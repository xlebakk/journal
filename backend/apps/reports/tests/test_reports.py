"""Reports, exports and the administrator's overview."""

import io
import time as clock
from collections.abc import Callable
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

import pytest
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.academics.models import Course, LessonType, WorkType
from apps.accounts import sessions
from apps.accounts.models import LoginEvent, Role, User
from apps.exams.models import Exam, ExamResult, StudentTarget
from apps.journal.models import Attendance, AttendanceStatus, Grade
from apps.journal.stats import StudentStats, summarise_group
from apps.schedule.models import Lesson, LessonStatus
from conftest import TODAY, MakeUser, enroll

ClientFor = Callable[..., APIClient]


def lesson(course: Course, day: date, status: str = LessonStatus.CONDUCTED, **extra: Any) -> Lesson:
    kind = LessonType.objects.get(short="Пр")
    return Lesson.objects.create(
        course=course,
        date=day,
        start_time=time(14),
        end_time=time(15, 30),
        teacher=extra.pop("teacher", course.teacher),
        lesson_type=kind,
        planned_date=day,
        planned_start_time=time(14),
        planned_end_time=time(15, 30),
        status=status,
        **extra,
    )


def grade(l: Lesson, student: User, value: int) -> Grade:  # noqa: E741
    work = WorkType.objects.order_by("name").first()
    assert work is not None
    return Grade.objects.create(
        lesson=l, student=student, value=value, scale="100", work_type=work,
        weight=Decimal(1), position=1, created_by=l.teacher,
    )  # fmt: skip


def mark(l: Lesson, student: User, status: str) -> Attendance:  # noqa: E741
    return Attendance.objects.create(lesson=l, student=student, status=status, marked_by=l.teacher)


def expire_reauth(client: APIClient) -> None:
    session = client.session
    session[sessions.REAUTH_AT] = clock.time() - 600
    session.save()


@pytest.fixture
def filled(
    course: Course, student: User, make_user: MakeUser, frozen_today: date
) -> dict[str, Any]:
    """Two students, two conducted lessons and one planned lesson a week ago."""
    second = make_user(Role.STUDENT, last_name="Ганиева", first_name="Мадина")
    enroll(course.group, second)
    first_lesson = lesson(course, TODAY - timedelta(days=7), topic="Дроби")
    second_lesson = lesson(course, TODAY - timedelta(days=6))
    lesson(course, TODAY - timedelta(days=5), status=LessonStatus.PLANNED)
    grade(first_lesson, student, 90)
    grade(second_lesson, student, 70)
    grade(first_lesson, second, 40)
    mark(first_lesson, student, AttendanceStatus.PRESENT)
    mark(second_lesson, student, AttendanceStatus.PRESENT)
    mark(first_lesson, second, AttendanceStatus.PRESENT)
    mark(second_lesson, second, AttendanceStatus.ABSENT)
    return {"second": second}


def test_summarise_group_formula() -> None:
    a = StudentStats(
        average=Decimal("90.00"), present=9, eligible=10, attendance_percent=Decimal(90)
    )
    b = StudentStats(average=Decimal("40.00"), present=5, excused=2, eligible=10,
                     attendance_percent=Decimal("62.50"))  # fmt: skip
    c = StudentStats()
    summary = summarise_group([a, b, c], attendance_threshold=80, low_below=Decimal(50))
    assert summary.average == Decimal("65.00")  # every student counts once
    assert summary.attendance_percent == Decimal("77.78")  # 14 / (20 − 2)
    assert (summary.students, summary.low_attendance, summary.low_average) == (3, 1, 1)


@pytest.mark.django_db
class TestCourseStatement:
    def test_json_and_files(
        self,
        course: Course,
        student: User,
        teacher: User,
        filled: dict[str, Any],
        client_for: ClientFor,
    ) -> None:
        client = client_for(teacher)
        url = f"/api/v1/reports/courses/{course.pk}"
        body = client.get(url, {"from": "2026-09-01", "to": str(TODAY)}).json()
        rows = {r["full_name"]: r for r in body["rows"]}
        assert rows[student.full_name]["average"] == "80.00"
        assert rows[filled["second"].full_name]["absent"] == 1
        assert body["summary"]["average"] == "60.00"
        assert body["summary"]["attendance_percent"] == "75.00"

        response = client.get(url, {"export": "xlsx"})
        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/vnd.openxmlformats")
        sheet = load_workbook(io.BytesIO(response.content)).worksheets[0]
        assert [c.value for c in sheet[1]][:3] == ["№", "ФИО", "Средний балл"]
        csv = client.get(url, {"export": "csv"})
        assert csv.content.startswith("﻿".encode())
        assert "Средний балл" in csv.content.decode("utf-8-sig")
        assert client.get(url, {"export": "pdf"}).status_code == 400

    def test_export_needs_fresh_password(
        self, course: Course, teacher: User, client_for: ClientFor, frozen_today: date
    ) -> None:
        client = client_for(teacher)
        expire_reauth(client)
        url = f"/api/v1/reports/courses/{course.pk}"
        assert client.get(url).status_code == 200
        response = client.get(url, {"export": "xlsx"})
        assert (response.status_code, response.json()) == (403, {"detail": "reauth_required"})

    def test_foreign_course_is_404(
        self, course: Course, make_user: MakeUser, client_for: ClientFor, frozen_today: date
    ) -> None:
        client = client_for(make_user(Role.TEACHER))
        assert client.get(f"/api/v1/reports/courses/{course.pk}").status_code == 404

    def test_formula_injection_is_neutralised(
        self,
        course: Course,
        teacher: User,
        make_user: MakeUser,
        client_for: ClientFor,
        frozen_today: date,
    ) -> None:
        evil = make_user(Role.STUDENT, last_name='=HYPERLINK("http://x")', first_name="Имя")
        enroll(course.group, evil)
        response = client_for(teacher).get(
            f"/api/v1/reports/courses/{course.pk}", {"export": "xlsx"}
        )
        sheet = load_workbook(io.BytesIO(response.content)).worksheets[0]
        names = [row[1].value for row in sheet.iter_rows(min_row=2)]
        assert any(str(n).startswith("'=HYPERLINK") for n in names)


@pytest.mark.django_db
class TestAdminReports:
    def test_performance_with_group_matrix(
        self, course: Course, filled: dict[str, Any], admin_client: APIClient
    ) -> None:
        body = admin_client.get(
            "/api/v1/admin/reports/performance", {"group": str(course.group_id)}
        ).json()
        assert [(c["subject_name"], c["average"], c["low_average"]) for c in body["courses"]] == [
            ("Математика", "60.00", 1)
        ]
        cells = {s["full_name"]: s["cells"][0]["average"] for s in body["students"]}
        assert sorted(cells.values()) == ["40.00", "80.00"]
        response = admin_client.get(
            "/api/v1/admin/reports/performance",
            {"group": str(course.group_id), "export": "xlsx"},
        )
        book = load_workbook(io.BytesIO(response.content))
        assert book.sheetnames == ["Курсы", "Ученики"]

    def test_fill_rate_by_teacher(
        self, course: Course, teacher: User, filled: dict[str, Any], admin_client: APIClient
    ) -> None:
        body = admin_client.get("/api/v1/admin/reports/fill-rate").json()
        row = next(r for r in body["rows"] if r["teacher"] == str(teacher.pk))
        assert (row["due"], row["conducted"], row["unfilled"], row["overdue"]) == (3, 2, 1, 1)
        assert row["no_topic"] == 1
        assert row["filled_percent"] == "66.7"

    def test_reversed_period_and_no_year(self, admin_client: APIClient, year: Any) -> None:
        response = admin_client.get(
            "/api/v1/admin/reports/fill-rate", {"from": "2026-12-01", "to": "2026-11-01"}
        )
        assert response.json() == {"to": ["period_reversed"]}
        year.is_current = False
        year.save()
        response = admin_client.get("/api/v1/admin/reports/fill-rate")
        assert response.json() == {"detail": ["no_academic_year"]}

    def test_student_summary_for_parents(
        self,
        course: Course,
        student: User,
        admin: User,
        filled: dict[str, Any],
        admin_client: APIClient,
    ) -> None:
        exam = Exam.objects.create(
            title="Пробный", subject=course.subject, date=TODAY - timedelta(days=3),
            max_score=200, created_by=admin,
        )  # fmt: skip
        exam.courses.set([course])
        ExamResult.objects.create(exam=exam, student=student, total=150, entered_by=admin)
        StudentTarget.objects.create(student=student, subject=course.subject, percent=80)
        body = admin_client.get(f"/api/v1/admin/reports/students/{student.pk}").json()
        assert body["student"]["groups"] == [course.group.name]
        assert body["subjects"][0]["average"] == "80.00"
        assert body["exams"][0] == {
            "subject_name": "Математика",
            "title": "Пробный",
            "date": str(TODAY - timedelta(days=3)),
            "total": 150,
            "max_score": 200,
            "percent": "75.0",
            "was_absent": False,
            "target_percent": 80,
        }

    def test_teacher_has_no_admin_reports(
        self, teacher: User, client_for: ClientFor, year: Any
    ) -> None:
        client = client_for(teacher)
        assert client.get("/api/v1/admin/reports/performance").status_code == 403
        assert client.get("/api/v1/admin/overview").status_code == 403


@pytest.mark.django_db
class TestOverview:
    def test_blocks(
        self,
        course: Course,
        teacher: User,
        filled: dict[str, Any],
        admin_client: APIClient,
    ) -> None:
        lesson(course, TODAY, status=LessonStatus.PLANNED)
        LoginEvent.objects.create(
            login_attempted="aliev.f", success=False, reason=LoginEvent.Reason.LOCKED
        )
        body = admin_client.get("/api/v1/admin/overview").json()
        assert body["lessons"]["total"] == 1
        assert [(u["teacher_name"], u["count"]) for u in body["unfilled"]] == [
            (teacher.full_name, 1)
        ]
        low = {r["full_name"]: r["attendance_percent"] for r in body["low_attendance"]}
        assert low == {filled["second"].full_name: "50.00"}
        assert body["blocked_logins"][0]["login"] == "aliev.f"
        assert len(body["audit"]) <= 20


@pytest.mark.django_db
class TestAuditExport:
    def test_export_with_reauth(self, admin_client: APIClient, student: User) -> None:
        admin_client.patch(
            f"/api/v1/admin/users/{student.pk}", {"last_name": "=cmd"}, format="json"
        )
        response = admin_client.get("/api/v1/admin/audit/export", {"export": "csv"})
        assert response.status_code == 200
        text = response.content.decode("utf-8-sig")
        assert "user.update" in text
        expire_reauth(admin_client)
        assert admin_client.get("/api/v1/admin/audit/export").status_code == 403

    def test_garbage_actor_is_400(self, admin_client: APIClient) -> None:
        assert admin_client.get("/api/v1/admin/audit", {"actor": "x"}).status_code == 400
