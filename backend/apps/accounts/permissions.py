"""Role permissions. The *active* role of the session (web or app) decides; it must be one of
the user's roles."""

from typing import Any

from django.conf import settings
from rest_framework.exceptions import NotAuthenticated, NotFound, PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.core.params import uuid_param

from . import sessions
from .models import AdminSection, Role, User, UserQuerySet


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


# Stage 16: which administration section a request belongs to, by its path. The longest
# prefix wins; "" — every administrator (the overview, the announcement feed); a path that
# is not listed — only the super administrator (deny by default).
ADMIN_PATHS: tuple[tuple[str, str], ...] = (
    ("/api/v1/admin/overview", ""),
    ("/api/v1/announcements", ""),
    ("/api/v1/admin/users", AdminSection.USERS),
    ("/api/v1/admin/import", AdminSection.USERS),
    ("/api/v1/admin/access-cards", AdminSection.USERS),
    ("/api/v1/admin/years", AdminSection.STRUCTURE),
    ("/api/v1/admin/terms", AdminSection.STRUCTURE),
    ("/api/v1/admin/subjects", AdminSection.STRUCTURE),
    ("/api/v1/admin/rooms", AdminSection.STRUCTURE),
    ("/api/v1/admin/work-types", AdminSection.STRUCTURE),
    ("/api/v1/admin/lesson-types", AdminSection.STRUCTURE),
    ("/api/v1/admin/holidays", AdminSection.STRUCTURE),
    ("/api/v1/admin/groups", AdminSection.STRUCTURE),
    ("/api/v1/admin/courses", AdminSection.STRUCTURE),
    ("/api/v1/admin/memberships", AdminSection.STRUCTURE),
    ("/api/v1/admin/teachers", AdminSection.STRUCTURE),
    ("/api/v1/admin/slots", AdminSection.SCHEDULE),
    ("/api/v1/admin/availability", AdminSection.SCHEDULE),
    ("/api/v1/admin/lessons", AdminSection.SCHEDULE),
    ("/api/v1/admin/schedule-requests", AdminSection.SCHEDULE),
    ("/api/v1/rooms", AdminSection.SCHEDULE),
    ("/api/v1/journal", AdminSection.JOURNAL),
    ("/api/v1/exams", AdminSection.EXAMS),
    ("/api/v1/admin/reports", AdminSection.REPORTS),
    ("/api/v1/reports", AdminSection.REPORTS),
    ("/api/v1/admin/payments", AdminSection.PAYMENTS),
    ("/api/v1/admin/announcements", AdminSection.ANNOUNCEMENTS),
    ("/api/v1/admin/audit", AdminSection.AUDIT),
    ("/api/v1/admin/login-events", AdminSection.AUDIT),
    ("/api/v1/admin/settings", AdminSection.SETTINGS),
)


def admin_section(path: str) -> str | None:
    """The section of an API path, "" for every administrator, None — super admin only."""
    best: tuple[int, str | None] = (-1, None)
    for prefix, section in ADMIN_PATHS:
        if (path == prefix or path.startswith(prefix + "/")) and len(prefix) > best[0]:
            best = (len(prefix), str(section))
    return best[1]


class IsAdmin(_HasActiveRole):
    """The active role is admin and the administrator has this path's section."""

    role = Role.ADMIN

    def has_permission(self, request: Request, view: Any) -> bool:
        if not super().has_permission(request, view):
            return False
        user = current_user(request)
        if user.is_superadmin:
            return True
        section = admin_section(request.path)
        return section == "" or (section is not None and section in user.admin_sections)


class SuperadminRequired(PermissionDenied):
    default_detail = "superadmin_required"
    default_code = "superadmin_required"


def require_superadmin(request: Request) -> None:
    """Administrators are managed only by the super administrator (stage 16)."""
    if not current_user(request).is_superadmin:
        raise SuperadminRequired()


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
    """Dangerous actions need the password entered within the last 5 minutes."""
    if not sessions.recently_reauthenticated(request, settings.REAUTH_VALID_SECONDS):
        raise ReauthRequired()
