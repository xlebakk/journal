"""Mock exams through the API (SPEC §6.4, §7.6, §8.7; decisions of stage 5)."""

import io
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.academics.models import Course
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.exams.models import Exam, ExamResult, ExamSection, StudentTarget
from conftest import TODAY, MakeUser, enroll

ClientFor = Callable[..., APIClient]
E = "/api/v1/exams"


def new_exam(client: APIClient, courses: list[Course], **extra: Any) -> Any:
    body = {
        "title": "Пробный ДТМ №1",
        "subject": str(courses[0].subject_id),
        "date": str(TODAY - timedelta(days=1)),
        "max_score": 100,
        "courses": [str(c.pk) for c in courses],
        **extra,
    }
    return client.post(E, body, format="json")


def put_result(client: APIClient, exam_id: Any, student: User, **body: Any) -> Any:
    return client.put(f"{E}/{exam_id}/results/{student.pk}", body, format="json")


@pytest.fixture
def exam(course: Course, admin: User, frozen_today: date) -> Exam:
    exam = Exam.objects.create(
        title="Пробный №1",
        subject=course.subject,
        date=TODAY - timedelta(days=1),
        max_score=100,
        created_by=admin,
    )
    exam.courses.set([course])
    return exam


@pytest.fixture
def shared(
    course: Course, other_group: Any, make_user: MakeUser, admin: User, frozen_today: date
) -> tuple[Exam, Course, User, User]:
    """One exam for two groups of two teachers."""
    other_teacher = make_user(Role.TEACHER, last_name="Носирова")
    other_student = make_user(Role.STUDENT, last_name="Бобоев")
    enroll(other_group, other_student)
    other_course = Course.objects.create(
        group=other_group, subject=course.subject, teacher=other_teacher
    )
    exam = Exam.objects.create(
        title="Общий",
        subject=course.subject,
        date=TODAY - timedelta(days=2),
        max_score=200,
        created_by=admin,
    )
    exam.courses.set([course, other_course])
    return exam, other_course, other_teacher, other_student


@pytest.mark.django_db
class TestExamCrud:
    def test_teacher_creates_for_own_course_with_sections(
        self, course: Course, teacher: User, client_for: ClientFor, frozen_today: date
    ) -> None:
        sections = [{"name": "Алгебра", "max_score": 60}, {"name": "Геометрия", "max_score": 40}]
        response = new_exam(client_for(teacher), [course], sections=sections)
        assert response.status_code == 201, response.json()
        body = response.json()
        assert [s["name"] for s in body["sections"]] == ["Алгебра", "Геометрия"]
        assert body["courses"][0]["group_name"] == course.group.name
        assert AuditLog.objects.filter(action="exam.create").count() == 1

    def test_foreign_course_and_subject_mismatch(
        self,
        course: Course,
        teacher: User,
        physics: Any,
        other_group: Any,
        make_user: MakeUser,
        client_for: ClientFor,
        frozen_today: date,
    ) -> None:
        foreign = Course.objects.create(
            group=other_group, subject=course.subject, teacher=make_user(Role.TEACHER)
        )
        client = client_for(teacher)
        response = new_exam(client, [course, foreign])
        assert response.json() == {"courses": ["not_your_course"]}
        response = new_exam(client, [course], subject=str(physics.pk))
        assert response.json() == {"courses": ["subject_mismatch"]}
        empty = client.post(
            E,
            {
                "title": "x",
                "subject": str(course.subject_id),
                "date": str(TODAY),
                "max_score": 10,
                "courses": [],
            },
            format="json",
        )
        assert empty.json() == {"courses": ["required"]}

    def test_sections_must_sum_to_max_and_be_unique(
        self, course: Course, teacher: User, client_for: ClientFor, frozen_today: date
    ) -> None:
        client = client_for(teacher)
        bad_sum = [{"name": "А", "max_score": 50}, {"name": "Б", "max_score": 40}]
        assert new_exam(client, [course], sections=bad_sum).json() == {
            "sections": ["sections_sum_mismatch"]
        }
        dup = [{"name": "А", "max_score": 50}, {"name": " а ", "max_score": 50}]
        assert new_exam(client, [course], sections=dup).json() == {
            "sections": ["duplicate_section"]
        }

    def test_foreign_teacher_and_student_do_not_see_exam(
        self, exam: Exam, student: User, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        stranger = client_for(make_user(Role.TEACHER))
        assert stranger.get(f"{E}/{exam.pk}").status_code == 404
        assert stranger.get(f"{E}/{exam.pk}/results").status_code == 404
        assert stranger.get(E).json() == []
        assert client_for(student).get(E).status_code == 403

    def test_structure_is_frozen_once_results_exist(
        self, exam: Exam, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        assert put_result(client, exam.pk, student, total=70).status_code == 200
        response = client.patch(f"{E}/{exam.pk}", {"version": 1, "max_score": 120}, format="json")
        assert response.json() == {"detail": ["exam_has_results"]}
        response = client.patch(f"{E}/{exam.pk}", {"version": 1, "title": "Новое"}, format="json")
        assert response.status_code == 200
        assert response.json()["title"] == "Новое"
        stale = client.patch(f"{E}/{exam.pk}", {"version": 1, "title": "x"}, format="json")
        assert stale.status_code == 409
        assert client.delete(f"{E}/{exam.pk}").json() == {"detail": ["exam_has_results"]}

    def test_delete_empty_exam(self, exam: Exam, teacher: User, client_for: ClientFor) -> None:
        assert client_for(teacher).delete(f"{E}/{exam.pk}").status_code == 204
        assert not Exam.objects.filter(pk=exam.pk).exists()
        assert AuditLog.objects.filter(action="exam.delete").count() == 1

    def test_teacher_cannot_touch_shared_exam_structure(
        self, shared: tuple[Exam, Course, User, User], teacher: User, client_for: ClientFor
    ) -> None:
        exam, *_ = shared
        client = client_for(teacher)
        response = client.patch(
            f"{E}/{exam.pk}",
            {"version": 1, "courses": [str(exam.courses.first().pk)]},  # type: ignore[union-attr]
            format="json",
        )
        assert response.status_code in (400, 403)
        assert client.delete(f"{E}/{exam.pk}").status_code == 403


@pytest.mark.django_db
class TestResults:
    def test_table_lists_members_on_exam_date(
        self,
        exam: Exam,
        course: Course,
        student: User,
        make_user: MakeUser,
        teacher: User,
        client_for: ClientFor,
    ) -> None:
        late = make_user(Role.STUDENT)
        enroll(course.group, late, joined=TODAY)
        body = client_for(teacher).get(f"{E}/{exam.pk}/results").json()
        assert [r["login"] for r in body["rows"]] == [student.login]
        assert body["editable"] is True
        assert body["needs_reason"] is False

    def test_put_total_and_version(
        self, exam: Exam, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        row = put_result(client, exam.pk, student, total=73).json()
        assert (row["total"], row["percent"], row["version"]) == (73, "73.0", 1)
        assert put_result(client, exam.pk, student, total=80).status_code == 409
        row = put_result(client, exam.pk, student, total=80, version=1).json()
        assert (row["total"], row["version"]) == (80, 2)
        assert AuditLog.objects.filter(action="exam.result_set").count() == 2

    def test_out_of_range_and_absent(
        self, exam: Exam, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        assert put_result(client, exam.pk, student, total=101).json() == {
            "total": ["score_out_of_range"]
        }
        row = put_result(client, exam.pk, student, was_absent=True).json()
        assert (row["total"], row["was_absent"], row["percent"]) == (None, True, None)

    def test_sections_make_the_total(
        self, exam: Exam, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        a = ExamSection.objects.create(exam=exam, name="Алгебра", max_score=60, position=0)
        b = ExamSection.objects.create(exam=exam, name="Геометрия", max_score=40, position=1)
        client = client_for(teacher)
        partial = put_result(client, exam.pk, student, sections={str(a.pk): 50})
        assert partial.json() == {"sections": ["all_sections_required"]}
        too_big = put_result(client, exam.pk, student, sections={str(a.pk): 61, str(b.pk): 1})
        assert too_big.json() == {"sections": ["score_out_of_range"]}
        row = put_result(
            client, exam.pk, student, total=1, sections={str(a.pk): 50, str(b.pk): 31}
        ).json()
        assert row["total"] == 81
        assert row["sections"] == {str(a.pk): 50, str(b.pk): 31}

    def test_future_exam_is_locked(
        self, exam: Exam, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        Exam.objects.filter(pk=exam.pk).update(date=TODAY + timedelta(days=1))
        client = client_for(teacher)
        assert client.get(f"{E}/{exam.pk}/results").json()["locked"] == "future"
        assert put_result(client, exam.pk, student, total=50).json() == {
            "detail": ["exam_in_future"]
        }

    def test_window_closed_teacher_403_admin_with_reason(
        self, exam: Exam, student: User, teacher: User, admin: User, client_for: ClientFor
    ) -> None:
        Exam.objects.filter(pk=exam.pk).update(date=TODAY - timedelta(days=8))
        response = put_result(client_for(teacher), exam.pk, student, total=50)
        assert response.status_code == 403
        assert response.json() == {"detail": "edit_window_closed"}
        boss = client_for(admin)
        assert boss.get(f"{E}/{exam.pk}/results").json()["needs_reason"] is True
        assert put_result(boss, exam.pk, student, total=50).json() == {
            "detail": ["reason_required"]
        }
        assert put_result(boss, exam.pk, student, total=50, reason="апелляция").status_code == 200
        log = AuditLog.objects.get(action="exam.result_set")
        assert log.reason == "апелляция"

    def test_clear(self, exam: Exam, student: User, teacher: User, client_for: ClientFor) -> None:
        client = client_for(teacher)
        put_result(client, exam.pk, student, total=40)
        url = f"{E}/{exam.pk}/results/{student.pk}/clear"
        assert client.post(url, {"version": 5}, format="json").status_code == 409
        assert client.post(url, {"version": 1}, format="json").status_code == 204
        assert not ExamResult.objects.exists()

    def test_shared_exam_teacher_sees_and_edits_own_groups_only(
        self,
        shared: tuple[Exam, Course, User, User],
        student: User,
        teacher: User,
        admin: User,
        client_for: ClientFor,
    ) -> None:
        exam, _, _, other_student = shared
        mine = client_for(teacher)
        rows = mine.get(f"{E}/{exam.pk}/results").json()["rows"]
        assert [r["login"] for r in rows] == [student.login]
        assert put_result(mine, exam.pk, other_student, total=10).json() == {
            "detail": ["student_not_in_exam"]
        }
        rows = client_for(admin).get(f"{E}/{exam.pk}/results").json()["rows"]
        assert {r["login"] for r in rows} == {student.login, other_student.login}


def csv_upload(text: str, name: str = "results.csv") -> io.BytesIO:
    data = io.BytesIO(text.encode("utf-8"))
    data.name = name
    return data


@pytest.mark.django_db
class TestImport:
    def test_preview_shows_errors_and_writes_nothing(
        self, exam: Exam, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        upload = csv_upload(f"Логин;Балл\n{student.login};77\nnobody;50\n{student.login};200\n")
        response = client.post(f"{E}/{exam.pk}/import", {"file": upload}, format="multipart")
        body = response.json()
        assert response.status_code == 200, body
        assert body["applied"] is False
        assert [r["issues"] for r in body["rows"]] == [
            [],
            ["student_not_in_exam"],
            ["score_out_of_range"],
        ]
        upload = csv_upload(f"Логин;Балл\n{student.login};77\nnobody;50\n")
        response = client.post(
            f"{E}/{exam.pk}/import", {"file": upload, "apply": "true"}, format="multipart"
        )
        assert response.json()["applied"] is False
        assert not ExamResult.objects.exists()

    def test_apply_xlsx_with_sections_and_absent(
        self,
        exam: Exam,
        course: Course,
        student: User,
        make_user: MakeUser,
        teacher: User,
        client_for: ClientFor,
    ) -> None:
        second = make_user(Role.STUDENT, last_name="Ганиева", first_name="Мадина")
        enroll(course.group, second)
        ExamSection.objects.create(exam=exam, name="Алгебра", max_score=60, position=0)
        ExamSection.objects.create(exam=exam, name="Геометрия", max_score=40, position=1)
        book = Workbook()
        sheet = book.worksheets[0]
        sheet.append(["ФИО", "Алгебра", "Геометрия", "Балл"])
        sheet.append([student.full_name, 55, 30, None])
        sheet.append([second.full_name, None, None, "н"])
        data = io.BytesIO()
        book.save(data)
        data.seek(0)
        data.name = "results.xlsx"
        response = client_for(teacher).post(
            f"{E}/{exam.pk}/import", {"file": data, "apply": "true"}, format="multipart"
        )
        body = response.json()
        assert body["applied"] is True, body
        totals = dict(ExamResult.objects.values_list("student__login", "total"))
        assert totals == {student.login: 85, second.login: None}

    def test_bad_file(self, exam: Exam, teacher: User, client_for: ClientFor) -> None:
        data = io.BytesIO(b"PK\x03\x04garbage")
        data.name = "x.xlsx"
        response = client_for(teacher).post(
            f"{E}/{exam.pk}/import", {"file": data}, format="multipart"
        )
        assert response.json() == {"file": ["unsupported_file"]}


@pytest.mark.django_db
class TestStats:
    def test_summary_distribution_groups(
        self,
        shared: tuple[Exam, Course, User, User],
        student: User,
        admin: User,
        client_for: ClientFor,
    ) -> None:
        exam, _, _, other_student = shared
        client = client_for(admin)
        put_result(client, exam.pk, student, total=150)
        put_result(client, exam.pk, other_student, total=99)
        body = client.get(f"{E}/{exam.pk}/stats").json()
        assert body["summary"] == {
            "count": 2,
            "absent": 0,
            "mean": "124.50",
            "median": "124.50",
            "min": 99,
            "max": 150,
        }
        assert body["mean_percent"] == "62.3"
        counts = {b["from_percent"]: b["count"] for b in body["distribution"]}
        assert counts[40] == 1  # 99 / 200 = 49.5 %
        assert counts[70] == 1  # 150 / 200 = 75 %
        assert sum(counts.values()) == 2
        assert [(g["group_name"], g["mean_percent"]) for g in body["groups"]] == [
            ("11-М вечерняя", "75.0"),
            ("11-Ф утренняя", "49.5"),
        ]

    def test_dynamics_over_exams(
        self, exam: Exam, course: Course, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        later = Exam.objects.create(
            title="Пробный №2",
            subject=course.subject,
            date=TODAY,
            max_score=50,
            created_by=teacher,
        )
        later.courses.set([course])
        client = client_for(teacher)
        put_result(client, exam.pk, student, total=60)
        put_result(client, later.pk, student, total=40)
        points = client.get(f"{E}/dynamics", {"subject": str(course.subject_id)}).json()
        assert [(p["title"], p["mean_percent"]) for p in points] == [
            ("Пробный №1", "60.0"),
            ("Пробный №2", "80.0"),
        ]
        assert client.get(f"{E}/dynamics", {"subject": "garbage"}).status_code == 400


@pytest.mark.django_db
class TestStudentExams:
    def test_own_results_with_target_and_change(
        self,
        exam: Exam,
        course: Course,
        student: User,
        teacher: User,
        make_user: MakeUser,
        client_for: ClientFor,
    ) -> None:
        later = Exam.objects.create(
            title="Пробный №2", subject=course.subject, date=TODAY, max_score=50, created_by=teacher
        )
        later.courses.set([course])
        classmate = make_user(Role.STUDENT)
        enroll(course.group, classmate)
        staff = client_for(teacher)
        put_result(staff, exam.pk, student, total=60)
        put_result(staff, later.pk, student, total=40)
        put_result(staff, exam.pk, classmate, total=99)
        StudentTarget.objects.create(student=student, subject=course.subject, percent=85)
        body = client_for(student).get("/api/v1/student/exams").json()
        assert len(body) == 1
        subject = body[0]
        assert subject["target_percent"] == 85
        assert [(e["percent"], e["change"]) for e in subject["exams"]] == [
            ("60.0", None),
            ("80.0", "20.0"),
        ]
        other = client_for(classmate).get("/api/v1/student/exams").json()
        assert [e["total"] for e in other[0]["exams"]] == [99]


@pytest.mark.django_db
class TestTargets:
    def test_admin_sets_targets(
        self, student: User, math: Any, physics: Any, admin_client: APIClient
    ) -> None:
        url = f"/api/v1/admin/users/{student.pk}/targets"
        body = [
            {"subject": str(math.pk), "percent": 85},
            {"subject": str(physics.pk), "percent": 70},
        ]
        response = admin_client.put(url, body, format="json")
        assert response.status_code == 200, response.json()
        assert len(admin_client.get(url).json()) == 2
        assert (
            admin_client.put(
                url, [{"subject": str(math.pk), "percent": 0}], format="json"
            ).status_code
            == 400
        )
        assert AuditLog.objects.filter(action="user.targets_update").count() == 1

    def test_not_a_student_is_404(self, teacher: User, admin_client: APIClient) -> None:
        assert admin_client.get(f"/api/v1/admin/users/{teacher.pk}/targets").status_code == 404
