"""The formulas on edge cases (no grades, only excused, transfer between groups)."""

from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

import pytest

from apps.academics.models import Course, Group, LessonType, WorkType
from apps.accounts.models import User
from apps.journal.models import Attendance, Grade
from apps.journal.stats import course_stats, low_threshold, rounded
from apps.schedule.models import Lesson, LessonStatus
from conftest import enroll


def make_lesson(
    course: Course, day: date, *, conducted: bool = True, counts: bool = True
) -> Lesson:
    lesson_type = LessonType.objects.filter(counts_attendance=counts).first()
    return Lesson.objects.create(
        course=course, date=day, start_time=time(14), end_time=time(15), teacher=course.teacher,
        lesson_type=lesson_type, status=LessonStatus.CONDUCTED if conducted else LessonStatus.PLANNED,
        planned_date=day, planned_start_time=time(14), planned_end_time=time(15),
    )  # fmt: skip


def mark(lesson: Lesson, student: User, status: str) -> None:
    Attendance.objects.create(
        lesson=lesson, student=student, status=status, marked_by=lesson.teacher
    )


def grade(
    lesson: Lesson, student: User, value: int, work: str, position: int = 1, **extra: Any
) -> Grade:
    work_type = WorkType.objects.get(name=work)
    return Grade.objects.create(
        lesson=lesson, student=student, value=value, scale="100", work_type=work_type,
        weight=work_type.weight, position=position, created_by=lesson.teacher, **extra,
    )  # fmt: skip


@pytest.mark.django_db
class TestAverage:
    def test_no_grades_is_none(self, course: Course, student: User) -> None:
        assert course_stats(course)[student.pk].average is None

    def test_weighted_average(self, course: Course, student: User) -> None:
        lesson = make_lesson(course, date(2026, 10, 5))
        grade(lesson, student, 80, "Ответ на занятии")  # ×1
        grade(lesson, student, 60, "Контрольная работа", position=2)  # ×2
        grade(lesson, student, 90, "Самостоятельная работа", position=3)  # ×1.5
        # (80 + 120 + 135) / 4.5 = 74.444…
        assert course_stats(course)[student.pk].average == Decimal("74.44")

    def test_deleted_grades_do_not_count(self, course: Course, student: User) -> None:
        from django.utils import timezone

        lesson = make_lesson(course, date(2026, 10, 5))
        grade(lesson, student, 100, "Ответ на занятии")
        grade(lesson, student, 0, "Ответ на занятии", position=2, deleted_at=timezone.now())
        assert course_stats(course)[student.pk].average == Decimal("100.00")

    def test_period_bounds_are_inclusive(self, course: Course, student: User) -> None:
        for day, value in [
            (date(2026, 9, 30), 10),
            (date(2026, 10, 1), 50),
            (date(2026, 10, 31), 70),
        ]:
            grade(make_lesson(course, day), student, value, "Ответ на занятии")
        stats = course_stats(course, date(2026, 10, 1), date(2026, 10, 31))
        assert stats[student.pk].average == Decimal("60.00")

    def test_rounding_is_half_up(self) -> None:
        assert rounded(Decimal("2.345")) == Decimal("2.35")
        assert rounded(Decimal("2.335")) == Decimal("2.34")

    def test_low_threshold_per_scale(self) -> None:
        assert low_threshold("100", 50) == 50
        assert low_threshold("5", 50) == Decimal("2.5")
        assert low_threshold("10", 50) == 5


@pytest.mark.django_db
class TestAttendance:
    def test_present_and_late_count_excused_is_removed(self, course: Course, student: User) -> None:
        days = [date(2026, 10, d) for d in (5, 6, 7, 8, 9)]
        for day, status in zip(
            days, ["present", "late", "absent", "excused", "present"], strict=True
        ):
            mark(make_lesson(course, day), student, status)
        stats = course_stats(course)[student.pk]
        # (2 present + 1 late) / (5 − 1 excused) = 75 %
        assert stats.attendance_percent == Decimal("75.00")
        assert (stats.excused, stats.absent, stats.eligible) == (1, 1, 5)

    def test_only_excused_gives_no_percentage(self, course: Course, student: User) -> None:
        mark(make_lesson(course, date(2026, 10, 5)), student, "excused")
        stats = course_stats(course)[student.pk]
        assert stats.attendance_percent is None
        assert stats.excused == 1

    def test_planned_and_non_counting_lessons_are_ignored(
        self, course: Course, student: User
    ) -> None:
        mark(make_lesson(course, date(2026, 10, 5)), student, "present")
        mark(make_lesson(course, date(2026, 10, 6), counts=False), student, "absent")
        make_lesson(course, date(2026, 10, 7), conducted=False)
        stats = course_stats(course)[student.pk]
        assert (stats.eligible, stats.attendance_percent) == (1, Decimal("100.00"))

    def test_transfer_counts_only_lessons_while_in_the_group(
        self, course: Course, other_group: Group, student: User
    ) -> None:
        membership = student.memberships.get()
        membership.left_on = date(2026, 10, 6)
        membership.save()
        enroll(other_group, student, joined=date(2026, 10, 7))
        mark(make_lesson(course, date(2026, 10, 5)), student, "present")
        mark(make_lesson(course, date(2026, 10, 6)), student, "absent")
        make_lesson(course, date(2026, 10, 7))  # after the transfer: not his lesson any more
        stats = course_stats(course)[student.pk]
        assert (stats.eligible, stats.attendance_percent) == (2, Decimal("50.00"))

    def test_query_count_does_not_grow(
        self, course: Course, make_user: Any, django_assert_max_num_queries: Any
    ) -> None:
        students = [make_user("student") for _ in range(10)]
        for s in students:
            enroll(course.group, s)
        for n in range(10):
            lesson = make_lesson(course, date(2026, 10, 1) + timedelta(days=n))
            for s in students:
                mark(lesson, s, "present")
                grade(lesson, s, 70 + n, "Ответ на занятии")
        with django_assert_max_num_queries(4):
            stats = course_stats(course)
        assert len(stats) == 11
