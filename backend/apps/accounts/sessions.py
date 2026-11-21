"""Session lifecycle and per-role timeouts (SPEC §2, §11).

Timeouts follow the *strictest* role of the account, not the active one: an
administrator switching to the teacher role keeps the administrator's limits.
"""

import hashlib
import time
from collections.abc import MutableMapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.contrib.auth import login, logout
from django.core.cache import cache
from django.http import HttpRequest
from django.utils import timezone

from apps.core.models import CenterSettings
from apps.core.request_info import client_ip, user_agent

from .models import Role, User, UserSession

# Session data keys.
USER_SESSION_ID = "user_session_id"
ACTIVE_ROLE = "active_role"
LAST_SEEN = "last_seen"
REAUTH_AT = "reauth_at"
PENDING_LOGIN = "pending_login"
TOTP_SETUP_SECRET = "totp_setup_secret"

LAST_SEEN_DB_WRITE_EVERY = 60  # seconds
APP_STATE_TTL = 3600


class AppState:
    """Short-lived per-session values (re-auth time, 2FA setup secret) of an app session.

    Web sessions keep them in the Django session; the app has no cookie, so they live in the
    cache under the session id. Losing them only means «enter the password again».
    """

    def __init__(self, session: UserSession) -> None:
        self.key = f"accounts:app-state:{session.pk}"

    def _data(self) -> dict[str, Any]:
        value = cache.get(self.key)
        return dict(value) if isinstance(value, dict) else {}

    def get(self, name: str, default: Any = None) -> Any:
        return self._data().get(name, default)

    def __setitem__(self, name: str, value: Any) -> None:
        data = self._data()
        data[name] = value
        cache.set(self.key, data, APP_STATE_TTL)

    def pop(self, name: str, default: Any = None) -> Any:
        data = self._data()
        value = data.pop(name, default)
        cache.set(self.key, data, APP_STATE_TTL)
        return value


def app_session(request: HttpRequest) -> UserSession | None:
    """The app session of a Bearer request (set by AppTokenMiddleware), or None."""
    value = getattr(request, "app_session", None)
    return value if isinstance(value, UserSession) else None


def state(request: HttpRequest) -> "AppState | MutableMapping[str, Any]":
    session = app_session(request)
    return AppState(session) if session is not None else request.session


def get_active_role(request: HttpRequest) -> str | None:
    session = app_session(request)
    if session is not None:
        return session.active_role or None
    value = request.session.get(ACTIVE_ROLE)
    return str(value) if value else None


def set_active_role(request: HttpRequest, role: str) -> None:
    session = app_session(request)
    if session is not None:
        session.active_role = role
        UserSession.objects.filter(pk=session.pk).update(active_role=role)
        return
    request.session[ACTIVE_ROLE] = role
    cycle_session_key(request)


@dataclass(frozen=True)
class Policy:
    idle_seconds: int | None
    absolute_seconds: int
    # False: the cookie lives until the browser closes.
    persistent_cookie: bool


def policy_for(user: User, remember: bool) -> Policy:
    s = CenterSettings.load()
    if user.is_admin:
        # «Запомнить устройство» does not apply to administrators.
        return Policy(s.admin_idle_minutes * 60, s.admin_absolute_hours * 3600, False)
    if user.has_role(Role.TEACHER):
        if remember:
            return Policy(None, s.teacher_remember_days * 86400, True)
        return Policy(s.teacher_idle_minutes * 60, s.teacher_absolute_hours * 3600, False)
    if remember:
        return Policy(None, s.student_remember_days * 86400, True)
    return Policy(None, s.student_absolute_hours * 3600, False)


def key_hash(session_key: str | None) -> str:
    return hashlib.sha256((session_key or "").encode()).hexdigest()


def start_session(request: HttpRequest, user: User, *, remember: bool) -> UserSession:
    """Logs the user in with a fresh session id and records the session."""
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    policy = policy_for(user, remember)
    request.session.set_expiry(policy.absolute_seconds if policy.persistent_cookie else 0)
    now = timezone.now()
    record = UserSession.objects.create(
        user=user,
        key_hash=key_hash(request.session.session_key),
        last_seen_at=now,
        expires_at=now + timedelta(seconds=policy.absolute_seconds),
        ip=client_ip(request),
        user_agent=user_agent(request),
        remember=policy.persistent_cookie,
    )
    request.session[USER_SESSION_ID] = str(record.id)
    request.session[ACTIVE_ROLE] = user.senior_role
    request.session[LAST_SEEN] = time.time()
    request.session[REAUTH_AT] = time.time()
    return record


def cycle_session_key(request: HttpRequest) -> None:
    """New session id for the same login (role switch, password change). Web only."""
    if app_session(request) is not None:
        return
    request.session.cycle_key()
    session_id = request.session.get(USER_SESSION_ID)
    if session_id:
        UserSession.objects.filter(pk=session_id).update(
            key_hash=key_hash(request.session.session_key)
        )


def current_session_id(request: HttpRequest) -> str | None:
    session = app_session(request)
    if session is not None:
        return str(session.pk)
    value = request.session.get(USER_SESSION_ID)
    return str(value) if value else None


def end_session(session: UserSession, reason: str) -> None:
    if session.ended_at is None:
        UserSession.objects.filter(pk=session.pk, ended_at__isnull=True).update(
            ended_at=timezone.now(), end_reason=reason
        )


def end_user_sessions(user: User, reason: str, *, except_id: str | None = None) -> int:
    """Ends sessions in the database; the middleware logs them out on their next request."""
    qs = UserSession.objects.filter(user=user, ended_at__isnull=True)
    if except_id:
        qs = qs.exclude(pk=except_id)
    return qs.update(ended_at=timezone.now(), end_reason=reason)


def logout_current(request: HttpRequest, reason: str) -> None:
    session = app_session(request)
    if session is not None:
        UserSession.objects.filter(pk=session.pk, ended_at__isnull=True).update(
            ended_at=timezone.now(), end_reason=reason
        )
        return
    session_id = current_session_id(request)
    if session_id:
        UserSession.objects.filter(pk=session_id, ended_at__isnull=True).update(
            ended_at=timezone.now(), end_reason=reason
        )
    logout(request)


def check_and_touch(request: HttpRequest, user: User) -> str | None:
    """Returns an end reason if the session must end now; otherwise refreshes activity."""
    session_id = current_session_id(request)
    record = (
        UserSession.objects.filter(pk=session_id, user=user, ended_at__isnull=True).first()
        if session_id
        else None
    )
    if record is None:
        return UserSession.EndReason.REVOKED
    if not user.can_log_in:
        return UserSession.EndReason.ACCOUNT_DISABLED
    if request.session.get(ACTIVE_ROLE) not in user.roles:
        return UserSession.EndReason.ROLES_CHANGED
    now = timezone.now()
    if now >= record.expires_at:
        return UserSession.EndReason.EXPIRED
    policy = policy_for(user, record.remember)
    last_seen = float(request.session.get(LAST_SEEN, 0))
    if policy.idle_seconds is not None and time.time() - last_seen > policy.idle_seconds:
        return UserSession.EndReason.IDLE
    request.session[LAST_SEEN] = time.time()
    if (now - record.last_seen_at).total_seconds() > LAST_SEEN_DB_WRITE_EVERY:
        UserSession.objects.filter(pk=record.pk).update(last_seen_at=now)
    return None


def mark_reauthenticated(request: HttpRequest) -> None:
    state(request)[REAUTH_AT] = time.time()


def recently_reauthenticated(request: HttpRequest, max_age: int) -> bool:
    return time.time() - float(state(request).get(REAUTH_AT, 0)) <= max_age
