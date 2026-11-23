"""Login, 2FA, password, role switch, own sessions."""

import time
from typing import Any

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import check_password as check_password
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.core.csrf import CsrfEnforcedMixin
from apps.core.models import CenterSettings
from apps.core.request_info import client_ip, user_agent
from apps.core.views_settings import login_video_url, logo_data_uri

from . import lockout, sessions, totp
from .middleware import totp_setup_required
from .models import LoginEvent, User, UserSession, normalize_login
from .permissions import current_user, require_recent_password
from .serializers import (
    BrandingSerializer,
    LoginSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    PasswordSerializer,
    RoleSwitchSerializer,
    SessionSerializer,
    TotpCodeSerializer,
)

PENDING_LOGIN_TTL = 300
# Hashed once: makes a login attempt for a non-existent user cost the same as a real one.
_DUMMY_HASH = make_password("dummy-password-for-timing-equalisation")

StepSerializer = inline_serializer("LoginStep", fields={"step": serializers.CharField()})


def invalid_credentials() -> Response:
    return Response({"detail": "invalid_credentials"}, status=status.HTTP_400_BAD_REQUEST)


def too_many_attempts(seconds: int) -> Response:
    minutes = lockout.minutes(seconds)
    return Response(
        {"detail": "too_many_attempts", "retry_after_minutes": minutes},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(minutes * 60)},
    )


def log_login(request: Request, login: str, user: User | None, success: bool, reason: str) -> None:
    LoginEvent.objects.create(
        login_attempted=login[:64],
        user=user,
        ip=client_ip(request),
        user_agent=user_agent(request),
        success=success,
        reason=reason,
    )


def check_password_step(request: Request, login: str, password: str) -> User | Response:
    """The first login step for the site and the app: limits, equal timing, the login journal.

    Returns the user whose password matched, or the error response to send.
    """
    wait = lockout.ip_over_limit_seconds(client_ip(request))
    if wait:
        log_login(request, login, None, False, LoginEvent.Reason.IP_LIMIT)
        return too_many_attempts(wait)
    wait = lockout.locked_seconds(login)
    if wait:
        log_login(request, login, None, False, LoginEvent.Reason.LOCKED)
        return too_many_attempts(wait)

    user = User.objects.filter(login=login).first()
    if user is None:
        check_password(password, _DUMMY_HASH)
        ok = False
    else:
        ok = user.check_password(password) and user.can_log_in
    if not ok or user is None:
        lockout.register_failure(login)
        log_login(request, login, user, False, LoginEvent.Reason.INVALID_CREDENTIALS)
        return invalid_credentials()
    lockout.reset_failures(login)
    return user


def check_second_factor(
    request: Request, user: User, code: str, attempts: int
) -> tuple[bool, Response | None]:
    """A TOTP or backup code. (True, None) — passed; (False, response) — refuse with it.

    `attempts` counts earlier wrong codes of this login; the last allowed one locks the login.
    """
    used_backup = False
    ok = totp.verify_totp(user, code)
    if not ok and totp.looks_like_backup_code(code):
        ok = used_backup = totp.use_backup_code(user, code)
    if ok:
        reason = LoginEvent.Reason.BACKUP_CODE if used_backup else LoginEvent.Reason.OK
        log_login(request, user.login, user, True, reason)
        return True, None
    if attempts + 1 >= settings.TOTP_MAX_ATTEMPTS:
        seconds = lockout.register_failure(user.login)
        log_login(request, user.login, user, False, LoginEvent.Reason.TOTP_LIMIT)
        return False, too_many_attempts(seconds or 60)
    log_login(request, user.login, user, False, LoginEvent.Reason.TOTP_INVALID)
    return False, Response({"detail": "invalid_code"}, status=400)


@method_decorator(ensure_csrf_cookie, name="get")
class LoginView(CsrfEnforcedMixin, APIView):
    """GET: what the login page shows + CSRF cookie. POST: login and password."""

    permission_classes = (AllowAny,)
    throttle_classes = ()  # own per-login and per-IP limits below

    @extend_schema(responses=BrandingSerializer)
    def get(self, request: Request) -> Response:
        s = CenterSettings.load()
        return Response(
            {
                "center_name": s.center_name,
                "contacts": s.contacts,
                "logo": logo_data_uri(s),
                "brand_color": s.brand_color,
                "login_video": login_video_url(s),
            }
        )

    @extend_schema(request=LoginSerializer, responses=StepSerializer)
    def post(self, request: Request) -> Response:
        form = LoginSerializer(data=request.data)
        if not form.is_valid():
            return invalid_credentials()
        login = normalize_login(form.validated_data["login"])
        checked = check_password_step(request, login, form.validated_data["password"])
        if isinstance(checked, Response):
            return checked
        user = checked
        remember = form.validated_data["remember"]
        if user.totp_enabled:
            request.session[sessions.PENDING_LOGIN] = {
                "user_id": str(user.pk),
                "at": time.time(),
                "remember": remember,
                "attempts": 0,
            }
            return Response({"step": "totp"})
        sessions.start_session(request, user, remember=remember)
        log_login(request, login, user, True, LoginEvent.Reason.OK)
        return Response({"step": "done"})


class TotpLoginView(CsrfEnforcedMixin, APIView):
    """Second login step: a 6-digit TOTP code or a backup code."""

    permission_classes = (AllowAny,)
    throttle_classes = ()

    @extend_schema(request=TotpCodeSerializer, responses=StepSerializer)
    def post(self, request: Request) -> Response:
        pending: dict[str, Any] | None = request.session.get(sessions.PENDING_LOGIN)
        if not pending or time.time() - float(pending["at"]) > PENDING_LOGIN_TTL:
            request.session.pop(sessions.PENDING_LOGIN, None)
            return Response({"detail": "totp_session_expired"}, status=400)
        user = User.objects.filter(pk=pending["user_id"]).first()
        if user is None or not user.can_log_in:
            request.session.pop(sessions.PENDING_LOGIN, None)
            return Response({"detail": "totp_session_expired"}, status=400)
        wait = lockout.locked_seconds(user.login)
        if wait:
            request.session.pop(sessions.PENDING_LOGIN, None)
            return too_many_attempts(wait)

        form = TotpCodeSerializer(data=request.data)
        code = form.validated_data["code"] if form.is_valid() else ""
        ok, refusal = check_second_factor(request, user, code, int(pending["attempts"]))
        if not ok:
            pending["attempts"] = int(pending["attempts"]) + 1
            if pending["attempts"] >= settings.TOTP_MAX_ATTEMPTS:
                request.session.pop(sessions.PENDING_LOGIN, None)
            else:
                request.session[sessions.PENDING_LOGIN] = pending
            return refusal or invalid_credentials()

        request.session.pop(sessions.PENDING_LOGIN, None)
        sessions.start_session(request, user, remember=bool(pending["remember"]))
        return Response({"step": "done"})


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        sessions.logout_current(request, UserSession.EndReason.LOGOUT)
        # The client also drops its query cache and service-worker caches.
        return Response(status=204, headers={"Clear-Site-Data": '"cache"'})


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=MeSerializer)
    def get(self, request: Request) -> Response:
        return Response(MeSerializer(current_user(request), context={"request": request}).data)


class PasswordChangeView(APIView):
    """Own password. The only call allowed while the temporary password is in force."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=PasswordChangeSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        user = current_user(request)
        wait = lockout.locked_seconds(user.login)
        if wait:
            return too_many_attempts(wait)
        current = request.data.get("current_password", "") if isinstance(request.data, dict) else ""
        if not isinstance(current, str) or not user.check_password(current):
            lockout.register_failure(user.login)
            return Response({"current_password": ["invalid_password"]}, status=400)
        form = PasswordChangeSerializer(data=request.data, context={"request": request})
        form.is_valid(raise_exception=True)
        with transaction.atomic():
            user.set_password(form.validated_data["new_password"])
            user.must_change_password = False
            user.password_changed_at = timezone.now()
            user.save(update_fields=["password", "must_change_password", "password_changed_at"])
            sessions.end_user_sessions(
                user,
                UserSession.EndReason.PASSWORD_CHANGED,
                except_id=sessions.current_session_id(request),
            )
            audit.record(request=request, action="auth.password_change", entity=user)
        # New session id and auth hash for the current session; others are already ended.
        if sessions.app_session(request) is None:
            update_session_auth_hash(request, user)
        sessions.cycle_session_key(request)
        sessions.mark_reauthenticated(request)
        lockout.reset_failures(user.login)
        return Response(status=204)


class RoleSwitchView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=RoleSwitchSerializer, responses=MeSerializer)
    def post(self, request: Request) -> Response:
        form = RoleSwitchSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        role = form.validated_data["role"]
        user = current_user(request)
        if role not in user.roles:
            return Response({"role": ["role_not_assigned"]}, status=400)
        sessions.set_active_role(request, role)
        return Response(MeSerializer(user, context={"request": request}).data)


class ReauthView(APIView):
    """Re-enter the password before a dangerous action."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=PasswordSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        user = current_user(request)
        wait = lockout.locked_seconds(user.login)
        if wait:
            return too_many_attempts(wait)
        form = PasswordSerializer(data=request.data)
        if not form.is_valid() or not user.check_password(form.validated_data["password"]):
            lockout.register_failure(user.login)
            return Response({"password": ["invalid_password"]}, status=400)
        sessions.mark_reauthenticated(request)
        return Response(status=204)


TotpSetupSerializer = inline_serializer(
    "TotpSetup",
    fields={
        "otpauth_uri": serializers.CharField(),
        "qr": serializers.CharField(),
        "secret": serializers.CharField(),
    },
)
BackupCodesSerializer = inline_serializer(
    "BackupCodes", fields={"backup_codes": serializers.ListField(child=serializers.CharField())}
)


class TotpSetupView(APIView):
    """GET: a new secret and QR. POST: confirm with a code → 2FA on + 10 backup codes.
    DELETE: turn 2FA off (only where it is optional; needs a fresh password)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=TotpSetupSerializer)
    def get(self, request: Request) -> Response:
        user = current_user(request)
        if user.totp_enabled:
            return Response({"detail": "totp_already_enabled"}, status=400)
        secret = totp.new_secret()
        sessions.state(request)[sessions.TOTP_SETUP_SECRET] = totp.encrypt_secret(secret)
        uri = totp.provisioning_uri(user, secret)
        return Response({"otpauth_uri": uri, "qr": totp.qr_svg_data_uri(uri), "secret": secret})

    @extend_schema(request=TotpCodeSerializer, responses=BackupCodesSerializer)
    def post(self, request: Request) -> Response:
        user = current_user(request)
        if user.totp_enabled:
            return Response({"detail": "totp_already_enabled"}, status=400)
        encrypted = sessions.state(request).get(sessions.TOTP_SETUP_SECRET)
        if not encrypted:
            return Response({"detail": "totp_setup_expired"}, status=400)
        form = TotpCodeSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        secret = totp.decrypt_secret(encrypted)
        counter = totp.matching_counter(secret, form.validated_data["code"])
        if counter is None:
            return Response({"code": ["invalid_code"]}, status=400)
        with transaction.atomic():
            user.totp_secret = encrypted
            user.totp_enabled = True
            user.totp_last_counter = counter
            user.save(update_fields=["totp_secret", "totp_enabled", "totp_last_counter"])
            codes = totp.generate_backup_codes(user)
            audit.record(request=request, action="auth.totp_enable", entity=user)
        sessions.state(request).pop(sessions.TOTP_SETUP_SECRET, None)
        return Response({"backup_codes": codes})

    @extend_schema(request=None, responses={204: None})
    def delete(self, request: Request) -> Response:
        user = current_user(request)
        if not user.totp_enabled:
            return Response(status=204)
        user.totp_enabled = False  # evaluate the policy as if 2FA were off
        required = totp_setup_required(user)
        user.totp_enabled = True
        if required:
            return Response({"detail": "totp_required"}, status=403)
        require_recent_password(request)
        with transaction.atomic():
            user.totp_enabled = False
            user.totp_secret = ""
            user.totp_last_counter = None
            user.save(update_fields=["totp_enabled", "totp_secret", "totp_last_counter"])
            user.backup_codes.all().delete()
            audit.record(request=request, action="auth.totp_disable", entity=user)
        return Response(status=204)


class BackupCodesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses=BackupCodesSerializer)
    def post(self, request: Request) -> Response:
        user = current_user(request)
        if not user.totp_enabled:
            return Response({"detail": "totp_not_enabled"}, status=400)
        require_recent_password(request)
        with transaction.atomic():
            codes = totp.generate_backup_codes(user)
            audit.record(request=request, action="auth.backup_codes_regenerate", entity=user)
        return Response({"backup_codes": codes})


class SessionListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=SessionSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = UserSession.objects.filter(user=current_user(request), ended_at__isnull=True)
        context = {"current_session_id": sessions.current_session_id(request)}
        return Response(SessionSerializer(qs, many=True, context=context).data)


class SessionDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, pk: str) -> Response:
        # Someone else's session id → 404, like any object outside the user's scope.
        record = get_object_or_404(
            UserSession, pk=pk, user=current_user(request), ended_at__isnull=True
        )
        if str(record.pk) == sessions.current_session_id(request):
            sessions.logout_current(request, UserSession.EndReason.LOGOUT)
        else:
            sessions.end_session(record, UserSession.EndReason.REVOKED)
        return Response(status=204)


class SessionEndOthersView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None,
        responses=inline_serializer("Ended", fields={"ended": serializers.IntegerField()}),
    )
    def post(self, request: Request) -> Response:
        ended = sessions.end_user_sessions(
            current_user(request),
            UserSession.EndReason.REVOKED,
            except_id=sessions.current_session_id(request),
        )
        return Response({"ended": ended})
