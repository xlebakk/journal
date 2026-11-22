"""Login of the Android app: the same steps as the site, but tokens instead of a cookie.

POST /auth/token        login + password → tokens, or {"step": "totp", "ticket": …}
POST /auth/token/totp   ticket + code → tokens
POST /auth/token/refresh  refresh → a new pair (the old refresh token is spent)
Logout is the usual POST /auth/logout with the Bearer header: it ends the app session.
"""

from django.conf import settings
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import lockout, tokens
from .models import LoginEvent, User, normalize_login
from .serializers import LoginSerializer
from .views_auth import (
    PENDING_LOGIN_TTL,
    check_password_step,
    check_second_factor,
    invalid_credentials,
    log_login,
    too_many_attempts,
)

TokenPairSerializer = inline_serializer(
    "TokenPair",
    fields={
        "step": serializers.CharField(),
        "access": serializers.CharField(),
        "access_expires_in": serializers.IntegerField(),
        "refresh": serializers.CharField(),
        "refresh_expires_at": serializers.DateTimeField(),
    },
)
TotpStepSerializer = inline_serializer(
    "TokenTotpStep", fields={"step": serializers.CharField(), "ticket": serializers.CharField()}
)
TicketSerializer = inline_serializer(
    "TokenTotpRequest",
    fields={"ticket": serializers.CharField(), "code": serializers.CharField(max_length=32)},
)
RefreshSerializer = inline_serializer(
    "TokenRefreshRequest", fields={"refresh": serializers.CharField(max_length=128)}
)


def _tokens(request: Request, user: User) -> Response:
    pair = tokens.start_app_session(request, user)
    return Response({"step": "done", **pair.as_dict()})


class TokenLoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()  # the login limits of the site apply

    @extend_schema(request=LoginSerializer, responses={200: TokenPairSerializer})
    def post(self, request: Request) -> Response:
        form = LoginSerializer(data=request.data)
        if not form.is_valid():
            return invalid_credentials()
        login = normalize_login(form.validated_data["login"])
        checked = check_password_step(request, login, form.validated_data["password"])
        if isinstance(checked, Response):
            return checked
        if checked.totp_enabled:
            return Response({"step": "totp", "ticket": tokens.totp_ticket(checked)})
        log_login(request, login, checked, True, LoginEvent.Reason.OK)
        return _tokens(request, checked)


class TokenTotpView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()

    @extend_schema(request=TicketSerializer, responses={200: TokenPairSerializer})
    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        read = tokens.read_ticket(str(data.get("ticket", "")), PENDING_LOGIN_TTL)
        if read is None:
            return Response({"detail": "totp_session_expired"}, status=400)
        user_id, nonce = read
        key = f"accounts:app-totp:{nonce}"
        attempts = cache.get(key, 0)
        user = User.objects.filter(pk=user_id).first()
        if attempts == "done" or user is None or not user.can_log_in:
            return Response({"detail": "totp_session_expired"}, status=400)
        if attempts >= settings.TOTP_MAX_ATTEMPTS:
            return Response({"detail": "totp_session_expired"}, status=400)
        wait = lockout.locked_seconds(user.login)
        if wait:
            return too_many_attempts(wait)
        ok, refusal = check_second_factor(request, user, str(data.get("code", "")), attempts)
        if not ok:
            cache.set(key, attempts + 1, PENDING_LOGIN_TTL)
            return refusal or invalid_credentials()
        cache.set(key, "done", PENDING_LOGIN_TTL)  # a ticket works once
        return _tokens(request, user)


class TokenRefreshView(APIView):
    """Rotation: every refresh token works once; a second use ends the session."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(request=RefreshSerializer, responses={200: TokenPairSerializer})
    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        try:
            pair = tokens.rotate(str(data.get("refresh", "")))
        except tokens.InvalidRefresh:
            return Response({"detail": "invalid_token"}, status=401)
        return Response({"step": "done", **pair.as_dict()})
