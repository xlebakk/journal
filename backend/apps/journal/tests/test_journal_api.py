"""Journal rules through the API (SPEC §10, §15)."""

import time as clock
from collections.abc import Callable
from datetime import date, time, timedelta
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.academics.models import Course, GradeScale, LessonType, WorkType
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.journal.models import Attendance, Grade
from apps.schedule.models import Lesson, LessonStatus
from conftest import PASSWORD, TODAY, MakeUser, enroll

ClientFor = Callable[..., APIClient]
J = "/api/v1/journal"


def lesson_on(course: Course, day: date, **extra: Any) -> Lesson:
    lesson_type = LessonType.objects.get(short="Пр")
    return Lesson.objects.create(
        course=course, date=day, start_time=time(14), end_time=time(15, 30),
        teacher=extra.pop("teacher", course.teacher), lesson_type=lesson_type,
        planned_date=day, planned_start_time=time(14), planned_end_time=time(15, 30), **extra,
    )  # fmt: skip


@pytest.fixture
def lesson(course: Course, frozen_today: date) -> Lesson:
    return lesson_on(course, TODAY - timedelta(days=1))


def add_grade(
    client: APIClient, lesson: Lesson, student: User, value: int = 85, **extra: Any
) -> Any:
    return client.post(
        f"{J}/lessons/{lesson.pk}/grades",
        {"student": str(student.pk), "value": value, **extra},
        format="json",
    )


def set_mark(client: APIClient, lesson: Lesson, student: User, status: str, **extra: Any) -> Any:
    return client.put(
        f"{J}/lessons/{lesson.pk}/attendance/{student.pk}",
        {"status": status, **extra},
        format="json",
    )


@pytest.mark.django_db
class TestWhoMayWrite:
    def test_teacher_grades_own_course(
        self, lesson: Lesson, teacher: User, student: User, client_for: ClientFor
    ) -> None:
        response = add_grade(client_for(teacher), lesson, student)
        assert response.status_code == 201, response.json()
        body = response.json()
        assert (body["value"], body["weight"], body["mine"]) == (85, "1.00", True)
        assert AuditLog.objects.filter(action="journal.grade_create").count() == 1

    def test_foreign_course_is_404(
        self, lesson: Lesson, student: User, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        stranger = make_user(Role.TEACHER)
        client = client_for(stranger)
        assert add_grade(client, lesson, student).status_code == 404
        assert client.get(f"{J}/lessons/{lesson.pk}").status_code == 404
        assert client.get(f"{J}/courses/{lesson.course_id}").status_code == 404

    def test_substitute_may_grade_in_his_lesson_only(
        self, course: Course, student: User, make_user: MakeUser, client_for: ClientFor,
        frozen_today: date,
    ) -> None:  # fmt: skip
        substitute = make_user(Role.TEACHER)
        theirs = lesson_on(course, TODAY - timedelta(days=1), teacher=substitute)
        other = lesson_on(course, TODAY - timedelta(days=2))
        client = client_for(substitute)
        assert add_grade(client, theirs, student).status_code == 201
        assert add_grade(client, other, student).status_code == 404

    def test_assistant_grades_but_edits_only_own(
        self, lesson: Lesson, teacher: User, student: User, make_user: MakeUser,
        client_for: ClientFor,
    ) -> None:  # fmt: skip
        assistant = make_user(Role.TEACHER)
        lesson.course.assistants.add(assistant)
        assistant_client, teacher_client = client_for(assistant), client_for(teacher)
        mine = add_grade(assistant_client, lesson, student, 70).json()
        theirs = add_grade(teacher_client, lesson, student, 90).json()
        response = assistant_client.patch(
            f"{J}/grades/{theirs['id']}", {"version": 1, "value": 10}, format="json"
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "not_your_grade"}
        response = assistant_client.patch(
            f"{J}/grades/{mine['id']}", {"version": 1, "value": 75}, format="json"
        )
        assert response.json()["value"] == 75
        # Attendance and topic: anyone of the course team.
        assert (
            set_mark(assistant_client, lesson, student, "late", late_minutes=10).status_code == 200
        )

    def test_student_cannot_touch_the_journal(
        self, lesson: Lesson, student: User, client_for: ClientFor
    ) -> None:
        client = client_for(student)
        assert add_grade(client, lesson, student, 100).status_code == 403
        assert set_mark(client, lesson, student, "present").status_code == 403
        assert client.get(f"{J}/lessons/{lesson.pk}").status_code == 403
        assert not Grade.objects.exists()


@pytest.mark.django_db
class TestEditWindow:
    @pytest.fixture
    def old_grade(self, course: Course, student: User, teacher: User, client_for: ClientFor) -> Any:
        old = lesson_on(course, TODAY - timedelta(days=8))
        # Given while the window was still open.
        grade = Grade.objects.create(
            lesson=old, student=student, value=60, scale="100", position=1, created_by=teacher,
            work_type=WorkType.objects.get(name="Ответ на занятии"), weight=1,
        )  # fmt: skip
        return grade

    def test_teacher_after_window_is_403(
        self, old_grade: Grade, teacher: User, client_for: ClientFor, frozen_today: date
    ) -> None:
        response = client_for(teacher).patch(
            f"{J}/grades/{old_grade.pk}", {"version": 1, "value": 99}, format="json"
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "edit_window_closed"}

    def test_last_day_of_the_window_is_open(
        self,
        course: Course,
        teacher: User,
        student: User,
        client_for: ClientFor,
        frozen_today: date,
    ) -> None:
        edge = lesson_on(course, TODAY - timedelta(days=7))
        assert add_grade(client_for(teacher), edge, student).status_code == 201

    def test_admin_needs_a_reason_after_the_window(
        self, old_grade: Grade, admin_client: APIClient, frozen_today: date
    ) -> None:
        url = f"{J}/grades/{old_grade.pk}"
        response = admin_client.patch(url, {"version": 1, "value": 99}, format="json")
        assert response.status_code == 400
        assert response.json() == {"detail": ["reason_required"]}
        response = admin_client.patch(
            url,
            {"version": 1, "value": 99, "reason": "ошибка при вводе, заявление ученика"},
            format="json",
        )
        assert response.status_code == 200
        entry = AuditLog.objects.get(action="journal.grade_update")
        assert entry.reason == "ошибка при вводе, заявление ученика"
        assert (entry.before["value"], entry.after["value"]) == (60, 99)  # type: ignore[index]

    def test_future_lesson_is_400(
        self,
        course: Course,
        teacher: User,
        student: User,
        client_for: ClientFor,
        frozen_today: date,
    ) -> None:
        future = lesson_on(course, TODAY + timedelta(days=1))
        response = add_grade(client_for(teacher), future, student)
        assert response.status_code == 400
        assert response.json() == {"detail": ["lesson_in_future"]}

    def test_cancelled_lesson_is_400(
        self,
        course: Course,
        teacher: User,
        student: User,
        client_for: ClientFor,
        frozen_today: date,
    ) -> None:
        cancelled = lesson_on(course, TODAY, status=LessonStatus.CANCELLED, cancel_reason="x")
        assert add_grade(client_for(teacher), cancelled, student).json() == {
            "detail": ["lesson_cancelled"]
        }


@pytest.mark.django_db
class TestGradeRules:
    def test_not_in_group_on_that_date(
        self, lesson: Lesson, teacher: User, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        late_joiner = make_user(Role.STUDENT)
        enroll(lesson.course.group, late_joiner, joined=TODAY)
        response = add_grade(client_for(teacher), lesson, late_joiner)
        assert response.status_code == 400
        assert response.json() == {"detail": ["student_not_in_group"]}

    @pytest.mark.parametrize(
        ("status", "allowed"),
        [("present", True), ("late", True), ("absent", False), ("excused", False)],
    )
    def test_grades_only_for_those_who_were_there(
        self,
        lesson: Lesson,
        teacher: User,
        student: User,
        client_for: ClientFor,
        status: str,
        allowed: bool,
    ) -> None:
        client = client_for(teacher)
        set_mark(
            client, lesson, student, status, **({"late_minutes": 5} if status == "late" else {})
        )
        response = add_grade(client, lesson, student)
        assert response.status_code == (201 if allowed else 400)

    def test_cannot_mark_absent_when_graded(
        self, lesson: Lesson, teacher: User, student: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        add_grade(client, lesson, student)
        assert set_mark(client, lesson, student, "absent").json() == {"detail": ["has_grades"]}

    def test_at_most_three(
        self, lesson: Lesson, teacher: User, student: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        for _ in range(3):
            assert add_grade(client, lesson, student).status_code == 201
        assert add_grade(client, lesson, student).json() == {"detail": ["too_many_grades"]}

    @pytest.mark.parametrize(("scale", "value", "ok"), [
        ("100", 0, True), ("100", 100, True), ("100", 101, False), ("100", -1, False),
        ("5", 2, True), ("5", 1, False), ("5", 6, False), ("10", 1, True), ("10", 11, False),
    ])  # fmt: skip
    def test_value_must_fit_the_year_scale(
        self, lesson: Lesson, teacher: User, student: User, client_for: ClientFor,
        scale: str, value: int, ok: bool,
    ) -> None:  # fmt: skip
        year = lesson.course.group.academic_year
        year.grade_scale = scale
        year.save()
        response = add_grade(client_for(teacher), lesson, student, value)
        assert response.status_code == (201 if ok else 400), response.json()
        if ok:
            assert Grade.objects.get().scale == scale

    def test_weight_is_copied_from_the_work_type(
        self, lesson: Lesson, teacher: User, student: User, client_for: ClientFor
    ) -> None:
        test_work = WorkType.objects.get(name="Контрольная работа")
        body = add_grade(client_for(teacher), lesson, student, work_type=str(test_work.pk)).json()
        test_work.weight = 5
        test_work.save()
        assert body["weight"] == "2.00"
        assert Grade.objects.get().weight == 2

    def test_soft_delete_and_restore(
        self, lesson: Lesson, teacher: User, student: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        grade = add_grade(client, lesson, student, 40).json()
        deleted = client.post(
            f"{J}/grades/{grade['id']}/delete", {"version": 1}, format="json"
        ).json()
        grid = client.get(
            f"{J}/courses/{lesson.course_id}", {"from": "2026-11-01", "to": "2026-11-30"}
        ).json()
        assert grid["grades"] == []
        assert grid["students"][0]["stats"]["average"] is None
        assert Grade.objects.filter(pk=grade["id"], deleted_at__isnull=False).exists()
        assert AuditLog.objects.filter(action="journal.grade_delete").exists()
        client.post(
            f"{J}/grades/{grade['id']}/restore", {"version": deleted["version"]}, format="json"
        )
        assert Grade.objects.alive().count() == 1


@pytest.mark.django_db
class TestLessonAndLocking:
    def test_conduct_needs_topic_type_and_attendance(
        self, lesson: Lesson, teacher: User, student: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        url = f"{J}/lessons/{lesson.pk}"
        assert client.post(f"{url}/conduct", {"version": 1}, format="json").json() == {
            "detail": ["topic_required"]
        }
        page = client.patch(
            url,
            {"version": 1, "topic": "Квадратные уравнения", "homework": "№ 12–15"},
            format="json",
        ).json()
        assert page["lesson"]["topic"] == "Квадратные уравнения"
        version = page["lesson"]["version"]
        assert client.post(f"{url}/conduct", {"version": version}, format="json").json() == {
            "detail": ["attendance_incomplete"]
        }
        client.post(f"{url}/attendance/all-present", {}, format="json")
        page = client.post(f"{url}/conduct", {"version": version}, format="json").json()
        assert page["lesson"]["status"] == "conducted"
        # Still editable inside the window (decision of stage 3).
        assert page["lesson"]["editable"] is True
        assert add_grade(client, lesson, student).status_code == 201

    def test_all_present_keeps_existing_marks(
        self,
        lesson: Lesson,
        teacher: User,
        student: User,
        make_user: MakeUser,
        client_for: ClientFor,
    ) -> None:
        other = make_user(Role.STUDENT)
        enroll(lesson.course.group, other)
        client = client_for(teacher)
        set_mark(client, lesson, student, "absent")
        client.post(f"{J}/lessons/{lesson.pk}/attendance/all-present", {}, format="json")
        marks = dict(Attendance.objects.values_list("student_id", "status"))
        assert marks == {student.pk: "absent", other.pk: "present"}

    def test_stale_versions_are_409(
        self, lesson: Lesson, teacher: User, student: User, client_for: ClientFor
    ) -> None:
        client = client_for(teacher)
        client.patch(f"{J}/lessons/{lesson.pk}", {"version": 1, "topic": "A"}, format="json")
        stale = client.patch(
            f"{J}/lessons/{lesson.pk}", {"version": 1, "topic": "B"}, format="json"
        )
        assert stale.status_code == 409
        assert stale.json() == {"detail": "version_conflict"}
        set_mark(client, lesson, student, "present")
        assert set_mark(client, lesson, student, "late").status_code == 409  # no version sent
        assert (
            set_mark(client, lesson, student, "late", version=1, late_minutes=3).status_code == 200
        )
        grade = add_grade(client, lesson, student).json()
        client.patch(f"{J}/grades/{grade['id']}", {"version": 1, "value": 50}, format="json")
        assert (
            client.patch(
                f"{J}/grades/{grade['id']}", {"version": 1, "value": 60}, format="json"
            ).status_code
            == 409
        )

    def test_lesson_page_shows_members_on_the_date(
        self,
        lesson: Lesson,
        teacher: User,
        student: User,
        make_user: MakeUser,
        client_for: ClientFor,
    ) -> None:
        newcomer = make_user(Role.STUDENT)
        enroll(lesson.course.group, newcomer, joined=TODAY)
        page = client_for(teacher).get(f"{J}/lessons/{lesson.pk}").json()
        assert [s["id"] for s in page["students"]] == [str(student.pk)]
        assert page["window_closes_on"] == (lesson.date + timedelta(days=7)).isoformat()


@pytest.mark.django_db
class TestGrid:
    def test_grid_content_and_flags(
        self, course: Course, teacher: User, student: User, admin_client: APIClient,
        client_for: ClientFor, frozen_today: date,
    ) -> None:  # fmt: skip
        old = lesson_on(course, TODAY - timedelta(days=10))
        recent = lesson_on(course, TODAY - timedelta(days=1))
        lesson_on(course, TODAY + timedelta(days=2))
        params = {"from": "2026-11-01", "to": "2026-11-30"}
        grid = client_for(teacher).get(f"{J}/courses/{course.pk}", params).json()
        flags = {row["date"]: (row["editable"], row["locked"]) for row in grid["lessons"]}
        assert flags[old.date.isoformat()] == (False, "window")
        assert flags[recent.date.isoformat()] == (True, None)
        assert flags[(TODAY + timedelta(days=2)).isoformat()] == (False, "future")
        assert grid["rules"] == {
            "scale": "100",
            "low_below": "50.00",
            "max_grades": 3,
            "edit_window_days": 7,
        }
        admin_grid = admin_client.get(f"{J}/courses/{course.pk}", params).json()
        old_row = next(row for row in admin_grid["lessons"] if row["date"] == old.date.isoformat())
        assert (old_row["editable"], old_row["needs_reason"]) == (True, True)

    def test_no_n_plus_one_and_fast(
        self, course: Course, teacher: User, make_user: MakeUser, client_for: ClientFor,
        frozen_today: date,
    ) -> None:  # fmt: skip
        """SPEC §15: 35 students × 60 lessons under 500 ms, queries do not grow with rows."""
        client = client_for(teacher)
        url = f"{J}/courses/{course.pk}"
        params = {"from": "2026-09-01", "to": "2026-12-31"}

        def measure() -> int:
            with CaptureQueriesContext(connection) as ctx:
                assert client.get(url, params).status_code == 200
            return len(ctx.captured_queries)

        lesson_on(course, date(2026, 9, 2))
        small = measure()

        students = [make_user(Role.STUDENT) for _ in range(34)]
        for s in students:
            enroll(course.group, s)
        work = WorkType.objects.first()
        assert work is not None
        lessons = [lesson_on(course, date(2026, 9, 3) + timedelta(days=n)) for n in range(59)]
        everyone = list(User.objects.filter(pk__in=course.group.memberships.values("student")))
        Attendance.objects.bulk_create(
            Attendance(lesson=x, student=s, status="present", marked_by=teacher)
            for x in lessons
            for s in everyone
        )
        Grade.objects.bulk_create(
            Grade(lesson=x, student=s, value=70, scale="100", work_type=work, weight=1, position=1, created_by=teacher)
            for x in lessons for s in everyone
        )  # fmt: skip
        big = measure()
        assert big == small, f"queries grew: {small} → {big}"

        started = clock.perf_counter()
        response = client.get(url, params)
        elapsed = clock.perf_counter() - started
        assert len(response.json()["lessons"]) == 60
        assert len(response.json()["students"]) == 35
        assert elapsed < 0.5, f"grid took {elapsed:.3f} s"


@pytest.mark.django_db
class TestTeacherToday:
    def test_states_unfilled_and_attention(
        self,
        course: Course,
        teacher: User,
        student: User,
        client_for: ClientFor,
        frozen_today: date,
    ) -> None:
        past = []
        for n in range(5, 0, -1):
            x = lesson_on(
                course, TODAY - timedelta(days=n), status=LessonStatus.CONDUCTED, topic="t"
            )
            Attendance.objects.create(
                lesson=x,
                student=student,
                status="absent" if n > 1 else "present",
                marked_by=teacher,
            )
            past.append(x)
        work = WorkType.objects.get(name="Ответ на занятии")
        for n, value in enumerate([30, 20]):
            Grade.objects.create(lesson=past[-1 - n] if n else past[-1], student=student, value=value, scale="100",
                                 work_type=work, weight=1, position=n + 1, created_by=teacher)  # fmt: skip
        lesson_on(course, TODAY - timedelta(days=6))  # planned, not filled
        lesson_on(course, TODAY)
        body = client_for(teacher).get("/api/v1/teacher/today").json()
        assert [x["state"] for x in body["lessons"]] in (["upcoming"], ["to_fill"])
        assert [x["date"] for x in body["unfilled"]][-1] == (TODAY - timedelta(days=6)).isoformat()
        reasons = {row["reason"] for row in body["attention"]}
        assert reasons == {"attendance"}
        assert body["attention"][0]["attendance_percent"] == "20.00"


@pytest.mark.django_db
class TestScaleLock:
    def test_scale_cannot_change_once_graded(
        self,
        lesson: Lesson,
        teacher: User,
        student: User,
        admin_client: APIClient,
        client_for: ClientFor,
    ) -> None:
        year = lesson.course.group.academic_year
        url = f"/api/v1/admin/years/{year.pk}"
        admin_client.post("/api/v1/auth/reauth", {"password": PASSWORD}, format="json")
        assert admin_client.patch(url, {"grade_scale": "5"}, format="json").status_code == 200
        admin_client.patch(url, {"grade_scale": "100"}, format="json")
        add_grade(client_for(teacher), lesson, student)
        response = admin_client.patch(url, {"grade_scale": GradeScale.FIVE}, format="json")
        assert response.json() == {"grade_scale": ["scale_locked"]}


@pytest.mark.django_db
def test_journal_course_list_is_scoped(
    course: Course,
    teacher: User,
    make_user: MakeUser,
    admin_client: APIClient,
    client_for: ClientFor,
) -> None:
    stranger = make_user(Role.TEACHER)
    assert len(client_for(teacher).get(f"{J}/courses").json()) == 1
    assert client_for(stranger).get(f"{J}/courses").json() == []
    assert len(admin_client.get(f"{J}/courses").json()) == 1
