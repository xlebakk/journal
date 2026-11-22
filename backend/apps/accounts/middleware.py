from collections.abc import Callable
from typing import Any

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.core.models import CenterSettings

from . import sessions, tokens
from .models import Role, User


class SessionPolicyMiddleware:
    """Ends sessions that were revoked, timed out or whose account/roles changed."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = request.user
        if user.is_authenticated and isinstance(user, User):
            reason = sessions.check_and_touch(request, user)
            if reason is not None:
                sessions.logout_current(request, reason)
                request.user = AnonymousUser()
        return self.get_response(request)


class AppTokenMiddleware:
    """`Authorization: Bearer <access>` from the Android app (SPEC §11).

    A Bearer request is authenticated by the token alone: cookies are ignored, and an invalid
    or expired token leaves the request anonymous (401; the app then refreshes).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            session = tokens.session_for_access(header.removeprefix("Bearer ").strip())
            request.user = session.user if session is not None else AnonymousUser()
            request.app_session = session  # type: ignore[attr-defined]
        return self.get_response(request)


def totp_setup_required(user: User) -> bool:
    """2FA is the user's choice unless the center requires it for one of their roles."""
    if user.totp_enabled:
        return False
    settings = CenterSettings.load()
    if user.is_admin and settings.require_admin_2fa:
        return True
    return user.has_role(Role.TEACHER) and settings.require_teacher_2fa


# URL names reachable while the user must first change the temporary password / set up 2FA.
PASSWORD_CHANGE_ALLOWED = frozenset(
    {"auth-me", "auth-logout", "auth-password", "auth-login", "auth-token-refresh"}
)
TOTP_SETUP_ALLOWED = PASSWORD_CHANGE_ALLOWED | {"auth-totp-setup"}


class ForcedActionMiddleware:
    """403 password_change_required / totp_setup_required for any other API call (SPEC §4)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_view(
        self, request: HttpRequest, view_func: Callable[..., Any], args: Any, kwargs: Any
    ) -> HttpResponse | None:
        user = request.user
        if not (user.is_authenticated and isinstance(user, User)):
            return None
        if not request.path_info.startswith("/api/"):
            return None
        name = request.resolver_match.url_name if request.resolver_match else None
        if user.must_change_password:
            if name not in PASSWORD_CHANGE_ALLOWED:
                return JsonResponse({"detail": "password_change_required"}, status=403)
        elif totp_setup_required(user) and name not in TOTP_SETUP_ALLOWED:
            return JsonResponse({"detail": "totp_setup_required"}, status=403)
        return None
