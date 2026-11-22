"""Tokens of the Android app.

* Access token — 10 minutes, kept only in the app's memory: a signed reference to the app
  session (`django.core.signing`), checked against the database on every request, so ending
  the session (logout, block, password change, «завершить сеанс») stops it at once.
* Refresh token — 30 days for every role (decision of stage 6), kept in the Android Keystore.
  Only its SHA-256 is stored. Every use rotates it; using an old one again ends the session.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from apps.core.request_info import client_ip, user_agent

from . import sessions
from .models import RefreshToken, User, UserSession

ACCESS_SALT = "accounts.app-access"
TOTP_SALT = "accounts.app-totp"
TOUCH_EVERY = timedelta(seconds=60)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_ttl() -> timedelta:
    return timedelta(days=settings.APP_REFRESH_DAYS)


@dataclass(frozen=True)
class TokenPair:
    access: str
    refresh: str
    refresh_expires_at: datetime

    def as_dict(self) -> dict[str, object]:
        return {
            "access": self.access,
            "access_expires_in": settings.APP_ACCESS_SECONDS,
            "refresh": self.refresh,
            "refresh_expires_at": self.refresh_expires_at,
        }


def _issue(session: UserSession) -> TokenPair:
    now = timezone.now()
    refresh = secrets.token_urlsafe(32)
    expires = now + refresh_ttl()
    RefreshToken.objects.create(session=session, token_hash=_hash(refresh), expires_at=expires)
    UserSession.objects.filter(pk=session.pk).update(expires_at=expires, last_seen_at=now)
    access = signing.dumps({"s": str(session.pk)}, salt=ACCESS_SALT)
    return TokenPair(access, refresh, expires)


def start_app_session(request: HttpRequest, user: User) -> TokenPair:
    now = timezone.now()
    session = UserSession.objects.create(
        user=user,
        kind=UserSession.Kind.APP,
        active_role=user.senior_role or "",
        last_seen_at=now,
        expires_at=now + refresh_ttl(),
        ip=client_ip(request),
        user_agent=user_agent(request),
        remember=True,
    )
    pair = _issue(session)
    # The password was just entered: dangerous actions do not ask again for 5 minutes.
    sessions.AppState(session)[sessions.REAUTH_AT] = now.timestamp()
    return pair


def session_for_access(token: str) -> UserSession | None:
    """The live app session behind an access token, or None (expired, forged, ended)."""
    try:
        data = signing.loads(token, salt=ACCESS_SALT, max_age=settings.APP_ACCESS_SECONDS)
    except signing.BadSignature:
        return None
    session_id = data.get("s") if isinstance(data, dict) else None
    if not isinstance(session_id, str):
        return None
    now = timezone.now()
    session = (
        UserSession.objects.select_related("user")
        .filter(pk=session_id, kind=UserSession.Kind.APP, ended_at__isnull=True)
        .first()
    )
    if session is None or session.expires_at <= now:
        return None
    reason = None
    if not session.user.can_log_in:
        reason = UserSession.EndReason.ACCOUNT_DISABLED
    elif session.active_role not in session.user.roles:
        reason = UserSession.EndReason.ROLES_CHANGED
    if reason is not None:
        end(session, reason)
        return None
    if now - session.last_seen_at > TOUCH_EVERY:
        UserSession.objects.filter(pk=session.pk).update(last_seen_at=now)
    return session


class InvalidRefresh(Exception):
    """Unknown, expired, used or belonging to an ended session: log in again."""


def rotate(refresh: str) -> TokenPair:
    now = timezone.now()
    ending: tuple[UserSession, str] | None = None
    with transaction.atomic():
        row = (
            RefreshToken.objects.select_for_update()
            .select_related("session__user")
            .filter(token_hash=_hash(refresh))
            .first()
        )
        if row is None:
            raise InvalidRefresh()
        session = row.session
        if session.ended_at is not None or row.expires_at <= now or session.expires_at <= now:
            raise InvalidRefresh()
        if row.used_at is not None:
            # A rotated token came back: someone holds a copy. End the whole chain.
            ending = (session, UserSession.EndReason.TOKEN_REUSE)
        elif not session.user.can_log_in:
            ending = (session, UserSession.EndReason.ACCOUNT_DISABLED)
        else:
            RefreshToken.objects.filter(pk=row.pk).update(used_at=now)
            return _issue(session)
    # Outside the transaction above, so the ending is not rolled back with the refusal.
    end(*ending)
    raise InvalidRefresh()


def end(session: UserSession, reason: str) -> None:
    UserSession.objects.filter(pk=session.pk, ended_at__isnull=True).update(
        ended_at=timezone.now(), end_reason=reason
    )


def totp_ticket(user: User) -> str:
    """The app's second login step: who passed the password, for 5 minutes."""
    return signing.dumps({"u": str(user.pk), "n": secrets.token_hex(8)}, salt=TOTP_SALT)


def read_ticket(ticket: str, max_age: int) -> tuple[str, str] | None:
    try:
        data = signing.loads(ticket, salt=TOTP_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    if not isinstance(data, dict) or "u" not in data or "n" not in data:
        return None
    return str(data["u"]), str(data["n"])
