"""Role permissions. The *active* role (session) decides, and must be one of the user's roles."""

from typing import Any

from django.conf import settings
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from . import sessions
from .models import Role, User


def current_user(request: Request) -> User:
    """The authenticated user, typed. Views behind IsAuthenticated/role permissions only."""
    user = request.user
    if not (user.is_authenticated and isinstance(user, User)):
        raise NotAuthenticated()
    return user


def active_role(request: Request) -> str | None:
    user = request.user
    if not (user.is_authenticated and isinstance(user, User)):
        return None
    role = request.session.get(sessions.ACTIVE_ROLE)
    return role if role in user.roles else None


class _HasActiveRole(BasePermission):
    role: str = ""

    def has_permission(self, request: Request, view: Any) -> bool:
        return active_role(request) == self.role


class IsAdmin(_HasActiveRole):
    role = Role.ADMIN


class IsTeacher(_HasActiveRole):
    role = Role.TEACHER


class IsStudent(_HasActiveRole):
    role = Role.STUDENT


class ReauthRequired(PermissionDenied):
    default_detail = "reauth_required"
    default_code = "reauth_required"


def require_recent_password(request: Request) -> None:
    """Dangerous actions need the password entered within the last 5 minutes (SPEC §8)."""
    if not sessions.recently_reauthenticated(request, settings.REAUTH_VALID_SECONDS):
        raise ReauthRequired()
