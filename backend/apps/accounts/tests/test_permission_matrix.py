"""Role × endpoint × whose object (SPEC §11, docs/security.md).

Every row is one expected status. Anonymous access is covered by the URL walker.
"""

from collections.abc import Callable

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from conftest import MakeUser

ClientFor = Callable[..., APIClient]

ROLES = ("admin", "teacher", "student")

# (method, url template, {role: expected status}); {other} = another user's id, {me} = own id.
MATRIX: list[tuple[str, str, dict[str, int]]] = [
    ("get", "/api/v1/me", {"admin": 200, "teacher": 200, "student": 200}),
    ("get", "/api/v1/auth/sessions", {"admin": 200, "teacher": 200, "student": 200}),
    ("get", "/api/v1/admin/users", {"admin": 200, "teacher": 403, "student": 403}),
    ("post", "/api/v1/admin/users", {"admin": 400, "teacher": 403, "student": 403}),
    ("get", "/api/v1/admin/users/{other}", {"admin": 200, "teacher": 403, "student": 403}),
    ("get", "/api/v1/admin/users/{me}", {"admin": 200, "teacher": 403, "student": 403}),
    ("patch", "/api/v1/admin/users/{other}", {"admin": 200, "teacher": 403, "student": 403}),
    ("patch", "/api/v1/admin/users/{me}", {"admin": 200, "teacher": 403, "student": 403}),
    (
        "post",
        "/api/v1/admin/users/{other}/reset-password",
        {"admin": 200, "teacher": 403, "student": 403},
    ),
    ("post", "/api/v1/admin/users/{other}/block", {"admin": 200, "teacher": 403, "student": 403}),
    ("post", "/api/v1/admin/users/{other}/archive", {"admin": 200, "teacher": 403, "student": 403}),
    (
        "post",
        "/api/v1/admin/users/{other}/reset-2fa",
        {"admin": 200, "teacher": 403, "student": 403},
    ),
    ("get", "/api/v1/admin/users/{other}/sessions", {"admin": 200, "teacher": 403, "student": 403}),
    ("get", "/api/v1/admin/audit", {"admin": 200, "teacher": 403, "student": 403}),
    ("get", "/api/v1/admin/login-events", {"admin": 200, "teacher": 403, "student": 403}),
    ("get", "/api/v1/schema/", {"admin": 200, "teacher": 403, "student": 403}),
    # Stage 2: structure and schedule.
    *[
        ("get", f"/api/v1/admin/{name}", {"admin": 200, "teacher": 403, "student": 403})
        for name in (
            "years",
            "terms",
            "subjects",
            "rooms",
            "work-types",
            "lesson-types",
            "holidays",
            "groups",
            "courses",
            "slots",
            "lessons",
            "schedule-requests",
            "teachers",
        )
    ],
    ("post", "/api/v1/admin/groups", {"admin": 400, "teacher": 403, "student": 403}),
    ("post", "/api/v1/admin/slots", {"admin": 400, "teacher": 403, "student": 403}),
    ("post", "/api/v1/admin/lessons", {"admin": 400, "teacher": 403, "student": 403}),
    ("get", "/api/v1/rooms", {"admin": 200, "teacher": 200, "student": 403}),
    ("get", "/api/v1/teacher/schedule", {"admin": 403, "teacher": 200, "student": 403}),
    ("get", "/api/v1/teacher/schedule-requests", {"admin": 403, "teacher": 200, "student": 403}),
    ("get", "/api/v1/student/schedule", {"admin": 403, "teacher": 403, "student": 200}),
    # Stage 3: journal.
    ("get", "/api/v1/journal/courses", {"admin": 200, "teacher": 200, "student": 403}),
    ("get", "/api/v1/teacher/today", {"admin": 403, "teacher": 200, "student": 403}),
]


@pytest.mark.django_db
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(
    ("method", "url", "expected"), MATRIX, ids=[f"{m} {u}" for m, u, _ in MATRIX]
)
def test_matrix(
    role: str,
    method: str,
    url: str,
    expected: dict[str, int],
    make_user: MakeUser,
    client_for: ClientFor,
) -> None:
    me = make_user(role)
    other = make_user(Role.STUDENT)
    client = client_for(me)
    response = getattr(client, method)(
        url.format(me=me.pk, other=other.pk), {} if method != "get" else None, format="json"
    )
    assert response.status_code == expected[role], response.content


@pytest.mark.django_db
def test_admin_in_teacher_role_has_no_admin_access(
    make_user: MakeUser, client_for: ClientFor
) -> None:
    director: User = make_user(Role.ADMIN, Role.TEACHER)
    client = client_for(director)
    client.post("/api/v1/auth/role", {"role": "teacher"}, format="json")
    assert client.get("/api/v1/admin/users").status_code == 403


@pytest.mark.django_db
def test_privileged_fields_cannot_be_set_through_self_service(
    student: User, client_for: ClientFor
) -> None:
    """There is no self-service endpoint that accepts roles / is_active."""
    client = client_for(student)
    for method in ("patch", "put", "post"):
        response = getattr(client, method)(
            "/api/v1/me", {"roles": ["admin"], "is_active": True}, format="json"
        )
        assert response.status_code == 405
    student.refresh_from_db()
    assert student.roles == ["student"]
