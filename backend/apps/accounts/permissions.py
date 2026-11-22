"""Role permissions. The *active* role of the session (web or app) decides; it must be one of
the user's roles."""

from typing import Any

from django.conf import settings
from rest_framework.exceptions import NotAuthenticated, NotFound, PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.core.params import uuid_param

from . import sessions
from .models import Role, User, UserQuerySet


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
    role = sessions.get_active_role(request)
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


class IsParent(_HasActiveRole):
    role = Role.PARENT


# The student's pages (stage 14): the student, or a parent looking at a child.
STUDENT_PAGES = (IsStudent | IsParent,)


def children_of(parent: User) -> "UserQuerySet":
    """The students linked to this parent; every other student must look like 404."""
    return User.objects.with_role(Role.STUDENT).filter(parent_links__parent=parent)


def subject_student(request: Request) -> User:
    """Whose data a student page shows: the student's own, or the parent's child from
    `?child=<id>` (the first child when it is not given). Not their child → 404."""
    me = current_user(request)
    if active_role(request) == Role.STUDENT:
        return me
    if active_role(request) != Role.PARENT:
        raise PermissionDenied()
    children = children_of(me).order_by("last_name", "first_name")
    child_id = uuid_param(request, "child")
    child = children.filter(pk=child_id).first() if child_id else children.first()
    if child is None:
        raise NotFound()
    return child


class ReauthRequired(PermissionDenied):
    default_detail = "reauth_required"
    default_code = "reauth_required"


def require_recent_password(request: Request) -> None:
    """Dangerous actions need the password entered within the last 5 minutes (SPEC §8)."""
    if not sessions.recently_reauthenticated(request, settings.REAUTH_VALID_SECONDS):
        raise ReauthRequired()
