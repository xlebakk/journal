"""Template changes, conflicts, exceptions, teacher requests."""

from collections.abc import Callable
from datetime import date, time, timedelta
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.academics.models import Course, Group, Room, Subject
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.schedule import services
from apps.schedule.models import Lesson, LessonStatus, ScheduleRequest, ScheduleSlot
from conftest import TODAY, MakeUser, enroll

ClientFor = Callable[..., APIClient]
SLOTS = "/api/v1/admin/slots"
LESSONS = "/api/v1/admin/lessons"


def slot_payload(course: Course, room: Room | None, **extra: Any) -> dict[str, Any]:
    return {
        "course": str(course.pk),
        "weekday": 1,
        "start_time": "14:00",
        "end_time": "15:30",
        "room": str(room.pk) if room else None,
        "valid_from": "2026-09-01",
        **extra,
    }


@pytest.fixture
def other_teacher(make_user: MakeUser) -> User:
    return make_user(Role.TEACHER, last_name="Ким", first_name="Сергей")


@pytest.fixture
def physics_course(other_group: Group, physics: Subject, other_teacher: User) -> Course:
    return Course.objects.create(group=other_group, subject=physics, teacher=other_teacher)


def first_lesson(slot: ScheduleSlot) -> Lesson:
    lesson = Lesson.objects.filter(slot=slot).order_by("date").first()
    assert lesson is not None
    return lesson


@pytest.mark.django_db
class TestSlotConflicts:
    def test_create_generates_lessons(
        self, admin_client: APIClient, course: Course, room: Room, frozen_today: date
    ) -> None:
        response = admin_client.post(SLOTS, slot_payload(course, room), format="json")
        assert response.status_code == 201, response.json()
        assert response.json()["plan"]["added"] == [
            (TODAY + timedelta(weeks=n)).isoformat() for n in range(4)
        ]
        assert Lesson.objects.count() == 4
        assert AuditLog.objects.filter(action="slot.create").exists()

    @pytest.mark.parametrize("kind", ["teacher", "room", "group"])
    def test_hard_conflicts_block(
        self,
        kind: str,
        admin_client: APIClient,
        slot: ScheduleSlot,
        physics_course: Course,
        physics: Subject,
        big_room: Room,
        teacher: User,
    ) -> None:
        if kind == "teacher":
            physics_course.teacher = teacher
            physics_course.save()
            payload = slot_payload(physics_course, big_room, start_time="15:00", end_time="16:00")
        elif kind == "room":
            payload = slot_payload(physics_course, slot.room, start_time="15:00", end_time="16:00")
        else:
            same_group = Course.objects.create(
                group=slot.course.group, subject=physics, teacher=physics_course.teacher
            )
            payload = slot_payload(same_group, big_room, start_time="15:00", end_time="16:00")
        response = admin_client.post(SLOTS, payload, format="json")
        assert response.status_code == 409
        body = response.json()
        assert body["detail"] == "schedule_conflict"
        assert body["conflicts"][0]["kind"] == kind
        assert body["conflicts"][0]["subject"] == "Математика"
        assert ScheduleSlot.objects.count() == 1

    def test_back_to_back_is_not_a_conflict(
        self, admin_client: APIClient, slot: ScheduleSlot, physics_course: Course
    ) -> None:
        payload = slot_payload(physics_course, slot.room, start_time="15:30", end_time="17:00")
        assert admin_client.post(SLOTS, payload, format="json").status_code == 201

    def test_student_in_two_groups_is_a_warning(
        self,
        admin_client: APIClient,
        slot: ScheduleSlot,
        physics_course: Course,
        big_room: Room,
        student: User,
    ) -> None:
        enroll(physics_course.group, student)
        payload = slot_payload(physics_course, big_room, start_time="15:00", end_time="16:00")
        response = admin_client.post(SLOTS, payload, format="json")
        assert response.status_code == 201
        warning = response.json()["warnings"][0]
        assert warning["kind"] == "students"
        assert warning["students"] == [student.short_name]

    def test_small_room_is_a_warning(
        self, admin_client: APIClient, course: Course, make_user: MakeUser, frozen_today: date
    ) -> None:
        tiny = Room.objects.create(name="Переговорная", capacity=1)
        enroll(course.group, make_user(Role.STUDENT))
        response = admin_client.post(SLOTS, slot_payload(course, tiny), format="json")
        assert response.status_code == 201
        assert response.json()["warnings"][0] == {
            "kind": "capacity",
            "date": TODAY.isoformat(),
            "room": "Переговорная",
            "capacity": 1,
            "students": 2,
        }

    def test_cancelled_lessons_do_not_conflict(
        self, admin_client: APIClient, slot: ScheduleSlot, physics_course: Course
    ) -> None:
        lesson = first_lesson(slot)
        lesson.status = LessonStatus.CANCELLED
        lesson.cancel_reason = "x"
        lesson.save()
        response = admin_client.post(
            LESSONS,
            {"course": str(physics_course.pk), "date": lesson.date.isoformat(),
             "start_time": "14:00", "end_time": "15:00", "room": str(slot.room_id)},
            format="json",
        )  # fmt: skip
        assert response.status_code == 201
        assert response.json()["lesson"]["is_extra"] is True


@pytest.mark.django_db
class TestTemplateChange:
    def test_change_needs_confirmation_with_dates(
        self, admin_client: APIClient, slot: ScheduleSlot
    ) -> None:
        ids = set(Lesson.objects.values_list("pk", flat=True))
        response = admin_client.patch(
            f"{SLOTS}/{slot.pk}", {"start_time": "16:00", "end_time": "17:30"}, format="json"
        )
        assert response.status_code == 409
        plan = response.json()["plan"]
        assert response.json()["detail"] == "confirmation_required"
        assert plan["updated"] == [(TODAY + timedelta(weeks=n)).isoformat() for n in range(4)]
        assert Lesson.objects.filter(start_time=time(16)).count() == 0

        response = admin_client.patch(
            f"{SLOTS}/{slot.pk}",
            {"start_time": "16:00", "end_time": "17:30", "confirm": True},
            format="json",
        )
        assert response.status_code == 200
        # Same rows, new time: nothing attached to them is lost.
        assert set(Lesson.objects.values_list("pk", flat=True)) == ids
        assert set(Lesson.objects.values_list("start_time", flat=True)) == {time(16)}

    def test_past_lessons_and_exceptions_are_kept(
        self, admin_client: APIClient, slot: ScheduleSlot
    ) -> None:
        past = services.generate_lessons(
            first=TODAY - timedelta(weeks=2), last=TODAY - timedelta(days=1)
        )
        assert past == 2
        moved, with_topic = Lesson.objects.filter(date__gte=TODAY).order_by("date")[:2]
        moved.start_time = time(9)
        moved.save()
        with_topic.topic = "Квадратные уравнения"
        with_topic.save()

        preview = admin_client.post(
            f"{SLOTS}/{slot.pk}/preview", {"weekday": 2}, format="json"
        ).json()
        assert preview["plan"]["kept_exceptions"] == [
            moved.date.isoformat(),
            with_topic.date.isoformat(),
        ]
        assert len(preview["plan"]["removed"]) == 2
        assert len(preview["plan"]["added"]) == 4
        assert Lesson.objects.filter(date__gte=TODAY).count() == 4  # preview changes nothing

        admin_client.patch(f"{SLOTS}/{slot.pk}", {"weekday": 2, "confirm": True}, format="json")
        moved.refresh_from_db()
        with_topic.refresh_from_db()
        assert moved.start_time == time(9)
        assert with_topic.date.isoweekday() == 1
        assert Lesson.objects.filter(date__lt=TODAY).count() == 2
        assert Lesson.objects.filter(date__gte=TODAY, date__week_day=3).count() == 4  # Tuesdays

    def test_delete_keeps_history(self, admin_client: APIClient, slot: ScheduleSlot) -> None:
        services.generate_lessons(first=TODAY - timedelta(weeks=1), last=TODAY - timedelta(days=1))
        assert admin_client.delete(f"{SLOTS}/{slot.pk}").status_code == 409
        response = admin_client.delete(f"{SLOTS}/{slot.pk}?confirm=true")
        assert response.status_code == 200
        assert not ScheduleSlot.objects.exists()
        remaining: list[tuple[Any, Any]] = list(Lesson.objects.values_list("date", "slot"))
        assert remaining == [(TODAY - timedelta(weeks=1), None)]


@pytest.mark.django_db
class TestExceptions:
    def test_cancel_with_reason_and_version(
        self, admin_client: APIClient, slot: ScheduleSlot
    ) -> None:
        lesson = first_lesson(slot)
        url = f"{LESSONS}/{lesson.pk}/cancel"
        assert admin_client.post(url, {"version": lesson.version}, format="json").status_code == 400
        response = admin_client.post(
            url, {"version": lesson.version, "reason": "болезнь преподавателя"}, format="json"
        )
        assert response.status_code == 200
        body = response.json()["lesson"]
        assert (body["status"], body["version"]) == ("cancelled", 2)
        entry = AuditLog.objects.get(action="lesson.cancel")
        assert entry.reason == "болезнь преподавателя"

    def test_stale_version_is_409(self, admin_client: APIClient, slot: ScheduleSlot) -> None:
        lesson = first_lesson(slot)
        url = f"{LESSONS}/{lesson.pk}/cancel"
        admin_client.post(url, {"version": 1, "reason": "a"}, format="json")
        response = admin_client.post(
            f"{LESSONS}/{lesson.pk}/restore", {"version": 1}, format="json"
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "version_conflict"}

    def test_move_keeps_planned_values(
        self, admin_client: APIClient, slot: ScheduleSlot, big_room: Room
    ) -> None:
        lesson = first_lesson(slot)
        new_date = lesson.date + timedelta(days=2)
        response = admin_client.post(
            f"{LESSONS}/{lesson.pk}/move",
            {
                "version": 1,
                "date": new_date.isoformat(),
                "start_time": "10:00",
                "end_time": "11:30",
                "room": str(big_room.pk),
            },
            format="json",
        )
        assert response.status_code == 200
        body = response.json()["lesson"]
        assert body["date"] == new_date.isoformat()
        assert body["planned_date"] == lesson.date.isoformat()
        assert body["is_moved"] is True
        assert body["is_room_changed"] is True
        assert body["planned_room_name"] == "101"
        assert services.generate_lessons() == 0  # no duplicate on the old date

    def test_move_into_a_conflict_is_blocked(
        self, admin_client: APIClient, slot: ScheduleSlot, physics_course: Course
    ) -> None:
        lesson = first_lesson(slot)
        Lesson.objects.create(
            course=physics_course, date=lesson.date + timedelta(days=1), start_time=time(10),
            end_time=time(11), room=slot.room, teacher=physics_course.teacher,
            planned_date=lesson.date, planned_start_time=time(10), planned_end_time=time(11),
        )  # fmt: skip
        response = admin_client.post(
            f"{LESSONS}/{lesson.pk}/move",
            {"version": 1, "date": (lesson.date + timedelta(days=1)).isoformat(),
             "start_time": "10:30", "end_time": "11:30", "room": str(slot.room_id)},
            format="json",
        )  # fmt: skip
        assert response.status_code == 409
        assert response.json()["conflicts"][0]["kind"] == "room"

    def test_substitute_and_back(
        self, admin_client: APIClient, slot: ScheduleSlot, other_teacher: User
    ) -> None:
        lesson = first_lesson(slot)
        url = f"{LESSONS}/{lesson.pk}/substitute"
        body = admin_client.post(
            url, {"version": 1, "teacher": str(other_teacher.pk)}, format="json"
        ).json()
        assert body["lesson"]["is_substituted"] is True
        assert body["lesson"]["teacher_name"] == "Ким С."
        body = admin_client.post(url, {"version": 2, "teacher": None}, format="json").json()
        assert body["lesson"]["is_substituted"] is False

    def test_student_cannot_substitute(
        self, admin_client: APIClient, slot: ScheduleSlot, student: User
    ) -> None:
        lesson = first_lesson(slot)
        response = admin_client.post(
            f"{LESSONS}/{lesson.pk}/substitute",
            {"version": 1, "teacher": str(student.pk)},
            format="json",
        )
        assert response.status_code == 400

    def test_conducted_lesson_is_frozen(self, admin_client: APIClient, slot: ScheduleSlot) -> None:
        lesson = first_lesson(slot)
        Lesson.objects.filter(pk=lesson.pk).update(status=LessonStatus.CONDUCTED)
        response = admin_client.post(
            f"{LESSONS}/{lesson.pk}/cancel", {"version": 1, "reason": "x"}, format="json"
        )
        assert response.status_code == 400

    def test_list_filters_and_range_limit(
        self, admin_client: APIClient, slot: ScheduleSlot, student: User
    ) -> None:
        params = {"from": TODAY.isoformat(), "to": (TODAY + timedelta(days=13)).isoformat()}
        assert len(admin_client.get(LESSONS, params).json()) == 2
        assert len(admin_client.get(LESSONS, {**params, "student": str(student.pk)}).json()) == 2
        assert admin_client.get(LESSONS, {**params, "group": "not-a-uuid"}).status_code == 400
        too_long = {"from": "2026-09-01", "to": "2026-12-31"}
        assert admin_client.get(LESSONS, too_long).status_code == 400


@pytest.mark.django_db
class TestTeacherRequests:
    def test_request_approve_applies_the_move(
        self, admin_client: APIClient, slot: ScheduleSlot, teacher: User, client_for: ClientFor
    ) -> None:
        lesson = first_lesson(slot)
        teacher_client = client_for(teacher)
        url = f"/api/v1/teacher/lessons/{lesson.pk}/requests"
        payload = {
            "kind": "move",
            "proposed_date": (lesson.date + timedelta(days=1)).isoformat(),
            "proposed_start_time": "16:00",
            "proposed_end_time": "17:30",
            "reason": "олимпиада в школе",
        }
        response = teacher_client.post(url, payload, format="json")
        assert response.status_code == 201, response.json()
        assert teacher_client.post(url, payload, format="json").status_code == 400  # one pending

        req = ScheduleRequest.objects.get()
        response = admin_client.post(
            f"/api/v1/admin/schedule-requests/{req.pk}/approve", {}, format="json"
        )
        assert response.json()["status"] == "approved"
        lesson.refresh_from_db()
        assert (lesson.date, lesson.start_time) == (
            lesson.planned_date + timedelta(days=1),
            time(16),
        )
        assert (
            teacher_client.get("/api/v1/teacher/schedule-requests").json()[0]["status"]
            == "approved"
        )

    def test_reject_and_withdraw(
        self, admin_client: APIClient, slot: ScheduleSlot, teacher: User, client_for: ClientFor
    ) -> None:
        lessons = Lesson.objects.filter(slot=slot).order_by("date")
        teacher_client = client_for(teacher)
        for lesson in lessons[:2]:
            teacher_client.post(
                f"/api/v1/teacher/lessons/{lesson.pk}/requests",
                {"kind": "cancel", "reason": "семинар"},
                format="json",
            )
        first, second = ScheduleRequest.objects.order_by("created_at")
        admin_client.post(
            f"/api/v1/admin/schedule-requests/{first.pk}/reject", {"comment": "нет"}, format="json"
        )
        teacher_client.post(f"/api/v1/teacher/schedule-requests/{second.pk}/withdraw")
        assert sorted(ScheduleRequest.objects.values_list("status", flat=True)) == [
            "rejected",
            "withdrawn",
        ]
        assert not Lesson.objects.filter(status=LessonStatus.CANCELLED).exists()

    def test_cannot_request_for_someone_elses_lesson(
        self, slot: ScheduleSlot, other_teacher: User, client_for: ClientFor
    ) -> None:
        lesson = first_lesson(slot)
        response = client_for(other_teacher).post(
            f"/api/v1/teacher/lessons/{lesson.pk}/requests",
            {"kind": "cancel", "reason": "x"},
            format="json",
        )
        assert response.status_code == 404
