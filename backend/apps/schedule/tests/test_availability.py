"""Stage 19: the schedule forms offer only what is free — pairs, rooms, teachers of the subject."""

from datetime import date, time
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, TeacherProfile, User
from apps.schedule.models import ScheduleSlot

URL = "/api/v1/admin/availability"
MONDAY = "2026-11-16"


def teacher_of(make_user: Any, last: str, subject: Any) -> User:
    user = make_user(Role.TEACHER, last_name=last)
    TeacherProfile.objects.get_or_create(user=user)[0].subjects.add(subject)
    return user


@pytest.mark.django_db
class TestAvailability:
    def test_a_day_offers_free_pairs_rooms_and_teachers(
        self,
        admin_client: APIClient,
        course: Any,
        slot: Any,
        room: Any,
        big_room: Any,
        math: Any,
        physics: Any,
        make_user: Any,
    ) -> None:
        # Another pair of the center (16:00–17:30) makes it a «usual» time to offer.
        other = ScheduleSlot.objects.create(
            course=course, weekday=3, start_time=time(16), end_time=time(17, 30),
            valid_from=date(2026, 9, 1),
        )  # fmt: skip
        assert other.pk
        free_math = teacher_of(make_user, "Свободный", math)
        teacher_of(make_user, "Физик", physics)
        body = admin_client.get(URL, {"course": course.pk, "date": MONDAY}).json()
        # Monday 14:00–15:30 is the group's own lesson: not offered, shown as busy.
        assert body["group_busy"] == [{"start": "14:00", "end": "15:30", "subject": "Математика"}]
        assert {"start": "14:00", "end": "15:30"} not in body["free_pairs"]
        assert {"start": "16:00", "end": "17:30"} in body["free_pairs"]
        assert body["rooms"] == []  # no time chosen yet

        at = admin_client.get(
            URL, {"course": course.pk, "date": MONDAY, "start": "14:30", "end": "15:00"}
        ).json()
        # Room 101 holds the Monday lesson then; only the hall is free.
        assert [r["name"] for r in at["rooms"]] == ["Актовый зал"]
        # Only teachers of the subject, and only free ones (the course teacher is busy).
        assert [t["full_name"] for t in at["teachers"]] == [free_math.full_name]

    def test_a_weekday_reads_the_template(
        self, admin_client: APIClient, course: Any, slot: Any
    ) -> None:
        body = admin_client.get(
            URL, {"course": course.pk, "weekday": 1, "valid_from": "2026-12-01"}
        ).json()
        assert body["group_busy"][0]["start"] == "14:00"
        # The slot being edited does not block itself.
        edited = admin_client.get(
            URL, {"course": course.pk, "weekday": 1, "exclude_slot": slot.pk}
        ).json()
        assert edited["group_busy"] == []

    def test_bad_input_is_400(self, admin_client: APIClient, course: Any) -> None:
        assert admin_client.get(URL, {"date": MONDAY}).status_code == 400
        assert admin_client.get(URL, {"course": course.pk, "weekday": 9}).status_code == 400
        bad = admin_client.get(
            URL, {"course": course.pk, "date": MONDAY, "start": "16:00", "end": "15:00"}
        )
        assert bad.json() == {"end": ["ends_before_start"]}

    def test_teachers_of_a_subject(
        self, admin_client: APIClient, math: Any, physics: Any, make_user: Any
    ) -> None:
        mine = teacher_of(make_user, "Алгебраист", math)
        teacher_of(make_user, "Механик", physics)
        names = [
            p["full_name"]
            for p in admin_client.get("/api/v1/admin/teachers", {"subject": math.pk}).json()
        ]
        assert names == [mine.full_name]
