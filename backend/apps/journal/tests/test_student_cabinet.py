"""The student's cabinet (SPEC §6): own data only, the same numbers as the journal."""

from collections.abc import Callable
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.academics.models import Course, Group, LessonType, Subject, Term, WorkType
from apps.accounts.models import Role, User
from apps.journal.models import Attendance, Grade
from apps.journal.stats import course_stats
from apps.schedule.models import Lesson, LessonStatus
from conftest import TODAY, MakeUser, enroll

ClientFor = Callable[..., APIClient]
S = "/api/v1/student"


def lesson_on(course: Course, day: date, **extra: Any) -> Lesson:
    return Lesson.objects.create(
        course=course, date=day, start_time=extra.pop("start", time(14)), end_time=time(15, 30),
        teacher=course.teacher, lesson_type=LessonType.objects.get(short="Пр"),
        planned_date=day, planned_start_time=time(14), planned_end_time=time(15, 30), **extra,
    )  # fmt: skip


def give(lesson: Lesson, student: User, value: int, position: int = 1, **extra: Any) -> Grade:
    work = WorkType.objects.get(name="Ответ на занятии")
    return Grade.objects.create(
        lesson=lesson, student=student, value=value, scale="100", work_type=work, weight=work.weight,
        position=position, created_by=lesson.teacher, **extra,
    )  # fmt: skip


def mark(lesson: Lesson, student: User, status: str, **extra: Any) -> Attendance:
    return Attendance.objects.create(
        lesson=lesson, student=student, status=status, marked_by=lesson.teacher, **extra
    )


@pytest.fixture
def classmate(course: Course, make_user: MakeUser) -> User:
    other = make_user(Role.STUDENT, last_name="Каримова", first_name="Мадина")
    enroll(course.group, other)
    return other


@pytest.fixture
def journal(
    course: Course, student: User, classmate: User, frozen_today: date
) -> dict[str, Lesson]:
    """Three conducted lessons, today's lesson with homework due on the next one."""
    a = lesson_on(
        course, TODAY - timedelta(days=7), status=LessonStatus.CONDUCTED, topic="Логарифмы"
    )
    b = lesson_on(course, TODAY - timedelta(days=3), status=LessonStatus.CONDUCTED, topic="Неравенства",
                  homework="№ 12–15")  # fmt: skip
    c = lesson_on(course, TODAY - timedelta(days=1), status=LessonStatus.CONDUCTED, topic="Модуль")
    today = lesson_on(course, TODAY)
    upcoming = lesson_on(course, TODAY + timedelta(days=2))
    mark(a, student, "present")
    mark(b, student, "late", late_minutes=10, comment="служебная заметка")
    mark(c, student, "absent")
    for lesson in (a, b, c):
        mark(lesson, classmate, "present")
    give(a, student, 90)
    give(b, student, 40, comment="разобрать ошибки")
    give(a, classmate, 10)
    return {"a": a, "b": b, "c": c, "today": today, "upcoming": upcoming}


@pytest.mark.django_db
class TestHome:
    def test_today_new_grades_homework_and_summary(
        self, journal: dict[str, Lesson], student: User, client_for: ClientFor
    ) -> None:
        body = client_for(student).get(f"{S}/home").json()
        assert [x["id"] for x in body["lessons_today"]] == [str(journal["today"].pk)]
        assert sorted(g["value"] for g in body["new_grades"]) == [40, 90]
        assert body["homework"] == [
            {
                "lesson": str(journal["b"].pk), "subject_name": "Математика",
                "assigned_on": journal["b"].date.isoformat(), "topic": "Неравенства",
                "homework": "№ 12–15", "due_on": TODAY.isoformat(),
            }
        ]  # fmt: skip
        summary = body["subjects"][0]
        stats = course_stats(
            journal["a"].course, date(2026, 9, 1), date(2027, 6, 30), [student.pk]
        )[student.pk]
        assert Decimal(summary["average"]) == stats.average == Decimal("65.00")
        assert summary["low"] is False

    def test_old_grades_are_not_new(
        self, journal: dict[str, Lesson], student: User, client_for: ClientFor
    ) -> None:
        from django.utils import timezone

        Grade.objects.filter(student=student, value=90).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        values = [g["value"] for g in client_for(student).get(f"{S}/home").json()["new_grades"]]
        assert values == [40]


@pytest.mark.django_db
class TestDiary:
    def test_week_with_topics_marks_and_own_grades(
        self, journal: dict[str, Lesson], student: User, client_for: ClientFor
    ) -> None:
        body = (
            client_for(student)
            .get(f"{S}/diary", {"week": (TODAY - timedelta(days=3)).isoformat()})
            .json()
        )
        assert body["week_start"] == (TODAY - timedelta(days=7)).isoformat()
        by_topic = {x["topic"]: x for x in body["lessons"]}
        assert by_topic["Логарифмы"]["attendance"] == "present"
        assert [g["value"] for g in by_topic["Логарифмы"]["grades"]] == [
            90
        ]  # not the classmate's 10
        assert by_topic["Неравенства"]["attendance"] == "late"
        assert by_topic["Неравенства"]["grades"][0]["comment"] == "разобрать ошибки"
        assert by_topic["Неравенства"]["grades"][0]["low"] is True
        assert "служебная заметка" not in str(body)

    def test_no_internal_fields(
        self, journal: dict[str, Lesson], student: User, client_for: ClientFor
    ) -> None:
        lesson = client_for(student).get(f"{S}/diary").json()["lessons"][0]
        for hidden in ("version", "course", "slot", "teacher", "course_teacher"):
            assert hidden not in lesson


@pytest.mark.django_db
class TestGrades:
    def test_subjects_with_grades_and_average(
        self, journal: dict[str, Lesson], student: User, client_for: ClientFor
    ) -> None:
        body = client_for(student).get(f"{S}/grades", {"term": "year"}).json()
        course = body["courses"][0]
        assert (course["subject_name"], course["average"]) == ("Математика", "65.00")
        assert [g["value"] for g in course["grades"]] == [90, 40]
        assert body["low_below"] == "50.00"

    def test_term_filter(
        self, journal: dict[str, Lesson], year: Any, student: User, client_for: ClientFor
    ) -> None:
        term = Term.objects.create(
            year=year, name="Модуль 1", starts_on=date(2026, 9, 1), ends_on=date(2026, 10, 31)
        )
        body = client_for(student).get(f"{S}/grades", {"term": str(term.pk)}).json()
        assert body["courses"] == [] or body["courses"][0]["grades"] == []
        assert body["terms"][0]["name"] == "Модуль 1"

    def test_someone_elses_grade_is_404(
        self, journal: dict[str, Lesson], student: User, classmate: User, client_for: ClientFor
    ) -> None:
        """SPEC §15: student A asks for student B's grade by id → 404."""
        mine = Grade.objects.get(student=student, value=90)
        theirs = Grade.objects.get(student=classmate)
        client = client_for(student)
        assert client.get(f"{S}/grades/{mine.pk}").json()["value"] == 90
        assert client.get(f"{S}/grades/{theirs.pk}").status_code == 404

    def test_deleted_grade_is_gone(
        self, journal: dict[str, Lesson], student: User, client_for: ClientFor
    ) -> None:
        from django.utils import timezone

        grade = Grade.objects.get(student=student, value=40)
        grade.deleted_at = timezone.now()
        grade.save()
        client = client_for(student)
        assert client.get(f"{S}/grades/{grade.pk}").status_code == 404
        assert (
            client.get(f"{S}/grades", {"term": "year"}).json()["courses"][0]["average"] == "90.00"
        )

    def test_old_course_stays_after_transfer(
        self, journal: dict[str, Lesson], student: User, other_group: Group, physics: Subject,
        make_user: MakeUser, client_for: ClientFor,
    ) -> None:  # fmt: skip
        membership = student.memberships.get()
        membership.left_on = TODAY - timedelta(days=1)
        membership.save()
        enroll(other_group, student, joined=TODAY)
        Course.objects.create(group=other_group, subject=physics, teacher=make_user(Role.TEACHER))
        names = {
            c["group_name"]
            for c in client_for(student).get(f"{S}/grades", {"term": "year"}).json()["courses"]
        }
        assert names == {"11-М вечерняя", "11-Ф утренняя"}


@pytest.mark.django_db
class TestAttendance:
    def test_per_subject_overall_and_calendar(
        self, journal: dict[str, Lesson], student: User, other_group: Group, physics: Subject,
        make_user: MakeUser, client_for: ClientFor,
    ) -> None:  # fmt: skip
        enroll(other_group, student)
        physics_course = Course.objects.create(
            group=other_group, subject=physics, teacher=make_user(Role.TEACHER)
        )
        p = lesson_on(
            physics_course, TODAY - timedelta(days=2), status=LessonStatus.CONDUCTED, start=time(10)
        )
        mark(p, student, "excused")
        body = client_for(student).get(f"{S}/attendance", {"month": TODAY.strftime("%Y-%m")}).json()
        maths = next(c for c in body["courses"] if c["subject_name"] == "Математика")
        # present + late = 2 of 3 conducted lessons
        assert maths["percent"] == "66.67"
        physics_row = next(c for c in body["courses"] if c["subject_name"] == "Физика")
        assert (physics_row["percent"], physics_row["excused"]) == (None, 1)
        # Overall: sums, not an average of percentages: 2 / (4 − 1) = 66.67
        assert (body["overall"], body["excused"]) == ("66.67", 1)
        days = {d["date"]: d for d in body["days"]}
        absent_day = days[journal["c"].date.isoformat()]
        assert absent_day["marks"] == [
            {"subject_short": "Мат", "subject_name": "Математика", "status": "absent"}
        ]
        assert days[journal["a"].date.isoformat()]["marks"] == []
        assert body["threshold"] == 80

    def test_invalid_month(
        self, journal: dict[str, Lesson], student: User, client_for: ClientFor
    ) -> None:
        assert client_for(student).get(f"{S}/attendance", {"month": "nope"}).status_code == 400


@pytest.mark.django_db
def test_profile(course: Course, student: User, client_for: ClientFor) -> None:
    profile = student.student_profile
    profile.target, profile.target_score, profile.school_grade = "ТУИТ", 180, 11
    profile.save()
    body = client_for(student).get(f"{S}/profile").json()
    assert body["groups"] == ["11-М вечерняя"]
    assert (body["target"], body["target_score"], body["school_grade"]) == ("ТУИТ", 180, 11)
    assert "parent_phone" not in body
    assert "admin_note" not in body


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["home", "diary", "grades", "attendance", "profile"])
def test_staff_cannot_open_the_student_cabinet(
    url: str, teacher: User, admin_client: APIClient, client_for: ClientFor, frozen_today: date
) -> None:
    assert client_for(teacher).get(f"{S}/{url}").status_code == 403
    assert admin_client.get(f"{S}/{url}").status_code == 403
