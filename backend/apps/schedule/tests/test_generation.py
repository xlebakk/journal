"""Generation of lessons from the week template: idempotency."""

from datetime import date, time, timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command

from apps.academics.models import Holiday
from apps.schedule import services
from apps.schedule.models import Lesson, LessonStatus, ScheduleSlot
from conftest import TODAY

MONDAYS = [TODAY + timedelta(weeks=n) for n in range(4)]


@pytest.mark.django_db
class TestGeneration:
    def test_four_weeks_ahead_on_the_slot_weekday(self, slot: ScheduleSlot) -> None:
        dates = list(Lesson.objects.filter(slot=slot).values_list("date", flat=True))
        assert dates == MONDAYS
        lesson = Lesson.objects.filter(slot=slot).first()
        assert lesson is not None
        assert (lesson.start_time, lesson.end_time) == (time(14, 0), time(15, 30))
        assert lesson.teacher_id == slot.course.teacher_id
        assert lesson.planned_date == lesson.date

    def test_second_run_creates_nothing(self, slot: ScheduleSlot) -> None:
        assert services.generate_lessons() == 0
        assert services.generate_lessons(slots=[slot]) == 0
        assert Lesson.objects.filter(slot=slot).count() == 4

    def test_moved_or_cancelled_lesson_is_not_recreated(self, slot: ScheduleSlot) -> None:
        first, second = Lesson.objects.filter(slot=slot)[:2]
        first.date = first.date + timedelta(days=2)
        first.save()
        second.status = LessonStatus.CANCELLED
        second.cancel_reason = "болезнь"
        second.save()
        assert services.generate_lessons() == 0
        assert Lesson.objects.filter(slot=slot).count() == 4

    def test_holidays_are_skipped(self, slot: ScheduleSlot, frozen_today: date) -> None:
        Lesson.objects.all().delete()
        Holiday.objects.create(date=MONDAYS[1], name="Праздник")
        services.generate_lessons()
        dates = set(Lesson.objects.values_list("date", flat=True))
        assert MONDAYS[1] not in dates
        assert len(dates) == 3

    def test_slot_period_and_year_bounds(self, course: Any, room: Any, frozen_today: date) -> None:
        ScheduleSlot.objects.create(
            course=course, weekday=3, start_time=time(10), end_time=time(11), room=room,
            valid_from=TODAY + timedelta(days=9), valid_to=TODAY + timedelta(days=16),
        )  # fmt: skip
        services.generate_lessons()
        assert list(Lesson.objects.values_list("date", flat=True)) == [
            TODAY + timedelta(days=9),
            TODAY + timedelta(days=16),
        ]
        # Beyond the academic year nothing is generated.
        Lesson.objects.all().delete()
        assert services.generate_lessons(first=date(2027, 6, 20)) == 0

    def test_archived_group_gets_no_lessons(self, slot: ScheduleSlot) -> None:
        Lesson.objects.all().delete()
        slot.course.group.is_archived = True
        slot.course.group.save()
        assert services.generate_lessons() == 0

    def test_command_for_cron(self, slot: ScheduleSlot) -> None:
        Lesson.objects.all().delete()
        out = StringIO()
        call_command("generate_lessons", stdout=out)
        assert "4" in out.getvalue()
        call_command("generate_lessons", stdout=out)
        assert Lesson.objects.count() == 4


def test_today_is_the_center_date_not_utc(settings: Any) -> None:
    """At 23:30 UTC it is already the next day in Tashkent (UTC+5)."""
    from datetime import UTC, datetime

    from django.utils import timezone

    late = datetime(2026, 11, 15, 23, 30, tzinfo=UTC)
    assert timezone.localdate(late) == date(2026, 11, 16)
    assert settings.TIME_ZONE == "Asia/Tashkent"
