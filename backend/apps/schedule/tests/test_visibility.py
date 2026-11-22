"""Who sees which lessons: own data only, others → 404 / absent."""

from collections.abc import Callable
from datetime import date, time, timedelta

import pytest
from rest_framework.test import APIClient

from apps.academics.models import Course, Group, Subject
from apps.accounts.models import Role, User
from apps.schedule import services
from apps.schedule.models import Lesson, ScheduleSlot
from conftest import TODAY, MakeUser, enroll

ClientFor = Callable[..., APIClient]
RANGE = {"from": TODAY.isoformat(), "to": (TODAY + timedelta(days=27)).isoformat()}


@pytest.fixture
def physics_slot(
    other_group: Group, physics: Subject, make_user: MakeUser, frozen_today: date
) -> ScheduleSlot:
    other_teacher = make_user(Role.TEACHER, last_name="Ким", first_name="Сергей")
    course = Course.objects.create(group=other_group, subject=physics, teacher=other_teacher)
    slot = ScheduleSlot.objects.create(
        course=course,
        weekday=3,
        start_time=time(10),
        end_time=time(11),
        valid_from=date(2026, 9, 1),
    )
    services.generate_lessons(slots=[slot])
    return slot


@pytest.mark.django_db
class TestTeacherSchedule:
    def test_own_course_only(
        self, teacher: User, slot: ScheduleSlot, physics_slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        lessons = client_for(teacher).get("/api/v1/teacher/schedule", RANGE).json()
        assert {lesson["subject_name"] for lesson in lessons} == {"Математика"}
        assert len(lessons) == 4

    def test_assisted_course_and_substitution(
        self, teacher: User, slot: ScheduleSlot, physics_slot: ScheduleSlot, make_user: MakeUser,
        client_for: ClientFor,
    ) -> None:  # fmt: skip
        assistant = make_user(Role.TEACHER)
        slot.course.assistants.add(assistant)
        substitute = make_user(Role.TEACHER)
        lesson = Lesson.objects.filter(slot=physics_slot).first()
        assert lesson is not None
        lesson.teacher = substitute
        lesson.save()
        assisted = client_for(assistant).get("/api/v1/teacher/schedule", RANGE).json()
        assert {x["subject_name"] for x in assisted} == {"Математика"}
        substituted = client_for(substitute).get("/api/v1/teacher/schedule", RANGE).json()
        assert [(x["subject_name"], x["is_substituted"]) for x in substituted] == [("Физика", True)]
        # The course teacher still sees the lesson, marked as substituted.
        owner = physics_slot.course.teacher
        marked = client_for(owner).get("/api/v1/teacher/schedule", RANGE).json()
        assert sum(x["is_substituted"] for x in marked) == 1


@pytest.mark.django_db
class TestStudentSchedule:
    def test_only_own_groups(
        self, student: User, slot: ScheduleSlot, physics_slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        lessons = client_for(student).get("/api/v1/student/schedule", RANGE).json()
        assert {x["subject_name"] for x in lessons} == {"Математика"}

    def test_no_internal_or_foreign_data(
        self, student: User, slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        lesson = client_for(student).get("/api/v1/student/schedule", RANGE).json()[0]
        for hidden in ("version", "course", "group", "slot", "teacher", "course_teacher"):
            assert hidden not in lesson
        assert lesson["teacher_name"] == slot.course.teacher.full_name

    def test_transfer_splits_the_schedule_by_date(
        self, student: User, slot: ScheduleSlot, physics_slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        membership = student.memberships.get()
        transfer_day = TODAY + timedelta(days=14)
        membership.left_on = transfer_day - timedelta(days=1)
        membership.save()
        enroll(physics_slot.course.group, student, joined=transfer_day)
        lessons = client_for(student).get("/api/v1/student/schedule", RANGE).json()
        before = {x["subject_name"] for x in lessons if x["date"] < transfer_day.isoformat()}
        after = {x["subject_name"] for x in lessons if x["date"] >= transfer_day.isoformat()}
        assert before == {"Математика"}
        assert after == {"Физика"}

    def test_cancelled_lesson_stays_visible(
        self, student: User, slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        lesson = Lesson.objects.filter(slot=slot).first()
        assert lesson is not None
        lesson.status = "cancelled"
        lesson.cancel_reason = "праздник"
        lesson.save()
        lessons = client_for(student).get("/api/v1/student/schedule", RANGE).json()
        assert [x["status"] for x in lessons].count("cancelled") == 1

    def test_me_lists_current_groups(
        self, student: User, slot: ScheduleSlot, client_for: ClientFor
    ) -> None:
        me = client_for(student).get("/api/v1/me").json()
        assert me["groups"] == [{"id": str(slot.course.group_id), "name": "11-М вечерняя"}]

    @pytest.mark.parametrize(
        "url", ["/api/v1/teacher/schedule", "/api/v1/admin/lessons", "/api/v1/admin/slots"]
    )
    def test_student_cannot_open_staff_endpoints(
        self, student: User, client_for: ClientFor, url: str, frozen_today: date
    ) -> None:
        assert client_for(student).get(url).status_code == 403
