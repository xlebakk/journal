"""Personal iCal subscription (stage 10)."""

from collections.abc import Callable
from urllib.parse import urlsplit

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.schedule import calendar
from apps.schedule.models import CalendarFeed, Lesson, LessonStatus, ScheduleSlot
from conftest import TODAY, MakeUser

ClientFor = Callable[..., APIClient]
ME = "/api/v1/me/calendar"


def issue(client: APIClient) -> str:
    response = client.post(ME)
    assert response.status_code == 201
    url = response.json()["url"]
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


def fetch(link: str) -> tuple[int, str]:
    response = APIClient().get(link)
    return response.status_code, response.content.decode() if response.status_code == 200 else ""


def unfold(body: str) -> str:
    return body.replace("\r\n ", "")


@pytest.mark.django_db
class TestFeed:
    def test_teacher_link_shows_own_lessons_in_utc(
        self, teacher: User, slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        link = issue(client_for(teacher))
        status, body = fetch(link)
        assert status == 200
        assert body.startswith("BEGIN:VCALENDAR\r\n")
        assert body.endswith("END:VCALENDAR\r\n")
        assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
        text = unfold(body)
        lesson = Lesson.objects.get(date=TODAY)
        assert f"UID:{lesson.pk}@journal" in text
        # 14:00 in Tashkent (UTC+5) is 09:00 UTC.
        assert "DTSTART:20261116T090000Z" in text
        assert "DTEND:20261116T103000Z" in text
        assert "SUMMARY:11-М вечерняя · Математика" in text
        assert "LOCATION:101" in text
        assert CalendarFeed.objects.get().last_used_at is not None

    def test_student_sees_own_groups_and_cancellations(
        self,
        student: User,
        slot: ScheduleSlot,
        make_user: MakeUser,
        client_for: ClientFor,
    ) -> None:
        lesson = Lesson.objects.get(date=TODAY)
        lesson.status = LessonStatus.CANCELLED
        lesson.cancel_reason = "болезнь, преподаватель"
        lesson.save()
        text = unfold(fetch(issue(client_for(student)))[1])
        assert "SUMMARY:Отменено: Математика" in text
        assert "STATUS:CANCELLED" in text
        assert "Причина отмены: болезнь\\, преподаватель" in text  # RFC 5545 escaping
        stranger = make_user(Role.STUDENT)
        assert "BEGIN:VEVENT" not in fetch(issue(client_for(stranger)))[1]

    def test_wrong_token_reissue_and_revoke(
        self, teacher: User, slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        first = issue(client)
        feed_path = first.split("?")[0]
        assert fetch(f"{feed_path}?token=0000")[0] == 404
        assert fetch(feed_path)[0] == 404
        second = issue(client)
        assert fetch(first)[0] == 404  # reissue kills the old link at once
        assert fetch(second)[0] == 200
        assert client.get(ME).json()["url"].endswith(second)
        assert client.delete(ME).status_code == 204
        assert fetch(second)[0] == 404
        assert client.get(ME).json()["url"] is None
        actions = list(
            AuditLog.objects.filter(action__startswith="calendar.")
            .order_by("id")
            .values_list("action", flat=True)
        )
        assert actions == ["calendar.issue", "calendar.reissue", "calendar.revoke"]
        reissue = AuditLog.objects.get(action="calendar.reissue")
        assert reissue.before == {"id": first.split("/")[-1].split(".ics")[0]}

    def test_link_dies_with_the_account_or_role(
        self, teacher: User, slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        link = issue(client_for(teacher))
        teacher.is_active = False
        teacher.save()
        assert fetch(link)[0] == 404
        teacher.is_active = True
        teacher.roles = [Role.STUDENT]
        teacher.save()
        assert fetch(link)[0] == 404

    def test_admin_has_no_feed(self, admin_client: APIClient) -> None:
        assert admin_client.get(ME).status_code == 403
        assert admin_client.post(ME).status_code == 403

    def test_by_active_role(self, make_user: MakeUser, client_for: ClientFor) -> None:
        director = make_user(Role.ADMIN, Role.TEACHER)
        client = client_for(director)
        client.post("/api/v1/auth/role", {"role": "teacher"}, format="json")
        issue(client)
        assert CalendarFeed.objects.get().role == "teacher"
        client.post("/api/v1/auth/role", {"role": "admin"}, format="json")
        assert client.get(ME).status_code == 403


def test_fold_keeps_multibyte_characters_whole() -> None:
    line = "SUMMARY:" + "Ж" * 60
    folded = calendar.fold(line)
    parts = folded.split("\r\n")
    assert all(len(p.encode()) <= 75 for p in parts)
    assert all(p.startswith(" ") for p in parts[1:])
    assert folded.replace("\r\n ", "") == line


def test_escape() -> None:
    assert calendar.escape("a;b,c\\d\ne") == "a\\;b\\,c\\\\d\\ne"


def test_token_is_bound_to_the_feed_and_the_key(settings: object) -> None:
    feed_id = "8c5d1d5e-3a43-4a8a-9b0f-1b8c8e2d6c11"
    token = calendar.token_for(feed_id)
    assert calendar.check_token(feed_id, token)
    assert not calendar.check_token("5f1b9a8e-0c4e-4d6e-8a2b-7c3d9e1f2a33", token)
    assert not calendar.check_token(feed_id, token[:-1] + "0")


def test_old_key_still_opens_links(settings: object) -> None:
    feed_id = "8c5d1d5e-3a43-4a8a-9b0f-1b8c8e2d6c11"
    token = calendar.token_for(feed_id)
    old_key = settings.SECRET_KEY  # type: ignore[attr-defined]
    settings.SECRET_KEY = "a-brand-new-secret-key-for-the-test-only"  # type: ignore[attr-defined]
    assert not calendar.check_token(feed_id, token)
    settings.SECRET_KEY_FALLBACKS = [old_key]  # type: ignore[attr-defined]
    assert calendar.check_token(feed_id, token)
