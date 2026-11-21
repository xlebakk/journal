"""Announcements: who sees what (SPEC §8.9)."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import Course
from apps.accounts.models import Role, User
from apps.announcements.models import Announcement, Audience
from apps.audit.models import AuditLog
from conftest import MakeUser, enroll

ClientFor = Callable[..., APIClient]
A = "/api/v1/admin/announcements"


def post(client: APIClient, **body: Any) -> Any:
    return client.post(A, {"title": "Заголовок", "body": "Текст", **body}, format="json")


@pytest.mark.django_db
class TestAdminCrud:
    def test_create_for_everyone_is_audited(self, admin_client: APIClient, admin: User) -> None:
        response = post(admin_client, pinned=True)
        assert response.status_code == 201, response.json()
        body = response.json()
        assert (body["audience"], body["pinned"], body["author_name"]) == (
            "all",
            True,
            "Каримова Д.",
        )
        assert AuditLog.objects.filter(action="announcement.create").count() == 1

    def test_validation(self, admin_client: APIClient) -> None:
        assert post(admin_client, audience="role").json() == {"role": ["role_required"]}
        assert post(admin_client, audience="role", role="admin").json() == {
            "role": ["role_required"]
        }
        assert post(admin_client, audience="groups").json() == {"groups": ["groups_required"]}
        now = timezone.now()
        response = post(
            admin_client,
            published_at=now.isoformat(),
            expires_at=(now - timedelta(hours=1)).isoformat(),
        )
        assert response.json() == {"expires_at": ["expires_before_published"]}

    def test_role_field_is_cleared_for_other_audiences(self, admin_client: APIClient) -> None:
        body = post(admin_client, audience="all", role="student").json()
        assert body["role"] == ""

    def test_others_cannot_write(self, teacher: User, client_for: ClientFor) -> None:
        assert post(client_for(teacher)).status_code == 403


@pytest.mark.django_db
class TestFeed:
    @pytest.fixture
    def board(
        self, course: Course, other_group: Any, admin: User, make_user: MakeUser
    ) -> dict[str, Announcement]:
        def make(title: str, **extra: Any) -> Announcement:
            groups = extra.pop("groups", [])
            a = Announcement.objects.create(author=admin, title=title, body="…", **extra)
            a.groups.set(groups)
            return a

        now = timezone.now()
        return {
            "all": make("Всем", pinned=True),
            "students": make("Ученикам", audience=Audience.ROLE, role=Role.STUDENT),
            "teachers": make("Преподавателям", audience=Audience.ROLE, role=Role.TEACHER),
            "group": make("Группе", audience=Audience.GROUPS, groups=[course.group]),
            "other": make("Другой группе", audience=Audience.GROUPS, groups=[other_group]),
            "future": make("Позже", published_at=now + timedelta(days=1)),
            "expired": make(
                "Было",
                published_at=now - timedelta(days=2),
                expires_at=now - timedelta(days=1),
            ),
        }

    def titles(self, client: APIClient, **params: Any) -> list[str]:
        return [a["title"] for a in client.get("/api/v1/announcements", params).json()]

    def test_student_sees_all_role_and_own_group(
        self, board: dict[str, Announcement], student: User, client_for: ClientFor
    ) -> None:
        client = client_for(student)
        assert set(self.titles(client)) == {"Всем", "Ученикам", "Группе"}
        assert self.titles(client)[0] == "Всем"  # pinned first
        assert self.titles(client, pinned="true") == ["Всем"]

    def test_teacher_sees_groups_of_own_courses(
        self, board: dict[str, Announcement], teacher: User, client_for: ClientFor
    ) -> None:
        assert set(self.titles(client_for(teacher))) == {"Всем", "Преподавателям", "Группе"}

    def test_left_student_does_not_see_group_news(
        self,
        board: dict[str, Announcement],
        course: Course,
        make_user: MakeUser,
        client_for: ClientFor,
    ) -> None:
        former = make_user(Role.STUDENT)
        today = timezone.localdate()
        enroll(
            course.group, former, joined=today - timedelta(days=30), left=today - timedelta(days=1)
        )
        assert set(self.titles(client_for(former))) == {"Всем", "Ученикам"}

    def test_admin_sees_live_ones(
        self, board: dict[str, Announcement], admin_client: APIClient
    ) -> None:
        titles = set(self.titles(admin_client))
        assert "Позже" not in titles
        assert "Было" not in titles
        assert len(admin_client.get(A).json()["results"]) == 7
