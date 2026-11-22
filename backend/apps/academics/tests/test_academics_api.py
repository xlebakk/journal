"""Structure of the center through the administrator API."""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Course, Group, GroupMembership, Subject
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.schedule.models import Lesson, LessonStatus, ScheduleSlot
from conftest import TODAY, MakeUser, enroll

API = "/api/v1/admin"


@pytest.mark.django_db
class TestYearsAndTerms:
    def test_years_cannot_overlap(self, admin_client: APIClient, year: AcademicYear) -> None:
        response = admin_client.post(
            f"{API}/years",
            {"name": "Пересекается", "starts_on": "2027-06-01", "ends_on": "2028-06-30"},
            format="json",
        )
        assert response.status_code == 400
        assert response.json() == {"non_field_errors": ["years_overlap"]}

    def test_one_current_year(self, admin_client: APIClient, year: AcademicYear) -> None:
        response = admin_client.post(
            f"{API}/years",
            {
                "name": "2027/2028",
                "starts_on": "2027-09-01",
                "ends_on": "2028-06-30",
                "is_current": True,
            },
            format="json",
        )
        assert response.status_code == 201
        year.refresh_from_db()
        assert year.is_current is False
        assert AuditLog.objects.filter(action="academic_year.create").exists()

    def test_terms_inside_year_and_not_overlapping(
        self, admin_client: APIClient, year: AcademicYear
    ) -> None:
        url = f"{API}/terms"
        ok = {
            "year": str(year.pk),
            "name": "Модуль 1",
            "starts_on": "2026-09-01",
            "ends_on": "2026-10-31",
        }
        assert admin_client.post(url, ok, format="json").status_code == 201
        overlap = {**ok, "name": "Модуль 2", "starts_on": "2026-10-15", "ends_on": "2026-12-31"}
        assert admin_client.post(url, overlap, format="json").json() == {
            "non_field_errors": ["terms_overlap"]
        }
        outside = {**ok, "name": "Лето", "starts_on": "2027-07-01", "ends_on": "2027-07-31"}
        assert admin_client.post(url, outside, format="json").json() == {
            "starts_on": ["outside_year"]
        }
        listed = admin_client.get(url, {"year": str(year.pk)}).json()
        assert [t["name"] for t in listed] == ["Модуль 1"]


@pytest.mark.django_db
class TestCatalogs:
    def test_crud_is_audited(self, admin_client: APIClient) -> None:
        created = admin_client.post(
            f"{API}/subjects", {"name": "Химия", "short_name": "Хим"}, format="json"
        )
        assert created.status_code == 201
        pk = created.json()["id"]
        admin_client.patch(f"{API}/subjects/{pk}", {"short_name": "Химия"}, format="json")
        entry = AuditLog.objects.get(action="subject.update")
        assert (entry.before, entry.after) == (
            {"name": "Химия", "short_name": "Хим", "is_archived": False},
            {"name": "Химия", "short_name": "Химия", "is_archived": False},
        )
        assert admin_client.delete(f"{API}/subjects/{pk}").status_code == 204
        assert AuditLog.objects.filter(action="subject.delete", entity_id=pk).exists()

    def test_names_are_unique_case_insensitive(
        self, admin_client: APIClient, math: Subject
    ) -> None:
        response = admin_client.post(
            f"{API}/subjects", {"name": "МАТЕМАТИКА", "short_name": "М2"}, format="json"
        )
        assert response.json() == {"non_field_errors": ["name_taken"]}

    def test_used_subject_cannot_be_deleted(self, admin_client: APIClient, course: Course) -> None:
        response = admin_client.delete(f"{API}/subjects/{course.subject_id}")
        assert response.status_code == 409
        assert response.json() == {"detail": "in_use"}
        assert Subject.objects.filter(pk=course.subject_id).exists()

    def test_default_lesson_and_work_types(self, admin_client: APIClient) -> None:
        lesson_types = admin_client.get(f"{API}/lesson-types").json()
        assert [t["short"] for t in lesson_types] == ["Лк", "Пр", "Сем", "КР", "ПТ", "Конс", "Повт"]
        weights = {w["name"]: w["weight"] for w in admin_client.get(f"{API}/work-types").json()}
        assert weights["Контрольная работа"] == "2.00"
        assert weights["Самостоятельная работа"] == "1.50"

    def test_work_type_weight_range(self, admin_client: APIClient) -> None:
        response = admin_client.post(
            f"{API}/work-types", {"name": "Ноль", "weight": "0"}, format="json"
        )
        assert response.json() == {"weight": ["weight_range"]}


@pytest.mark.django_db
class TestGroupsAndMembership:
    def test_add_member_and_no_overlapping_periods(
        self, admin_client: APIClient, group: Group, make_user: MakeUser
    ) -> None:
        student = make_user(Role.STUDENT)
        url = f"{API}/groups/{group.pk}/members"
        assert (
            admin_client.post(
                url, {"student": str(student.pk), "joined_on": "2026-09-01"}, format="json"
            ).status_code
            == 201
        )
        again = admin_client.post(
            url, {"student": str(student.pk), "joined_on": "2026-10-01"}, format="json"
        )
        assert again.json() == {"student": ["already_member"]}
        assert admin_client.get(f"{API}/groups/{group.pk}").json()["members_count"] == 1

    def test_only_students_can_be_members(
        self, admin_client: APIClient, group: Group, teacher: User
    ) -> None:
        url = f"{API}/groups/{group.pk}/members"
        response = admin_client.post(
            url, {"student": str(teacher.pk), "joined_on": "2026-09-01"}, format="json"
        )
        assert response.status_code == 400

    def test_transfer_closes_old_and_opens_new(
        self, admin_client: APIClient, group: Group, other_group: Group, student: User
    ) -> None:
        membership = enroll(group, student)
        response = admin_client.post(
            f"{API}/memberships/{membership.pk}/transfer",
            {"group": str(other_group.pk), "date": "2026-11-16"},
            format="json",
        )
        assert response.status_code == 201
        membership.refresh_from_db()
        assert membership.left_on == date(2026, 11, 15)
        new = GroupMembership.objects.get(group=other_group)
        assert new.joined_on == date(2026, 11, 16)
        entry = AuditLog.objects.get(action="group.member_transfer")
        assert entry.after is not None
        assert entry.after["closed"]["left_on"] == "2026-11-15"

    def test_leave_and_history(self, admin_client: APIClient, group: Group, student: User) -> None:
        membership = enroll(group, student)
        url = f"{API}/memberships/{membership.pk}/leave"
        assert admin_client.post(url, {"left_on": "2026-08-01"}, format="json").json() == {
            "left_on": ["left_before_joined"]
        }
        assert admin_client.post(url, {"left_on": "2026-10-31"}, format="json").status_code == 200
        history = admin_client.get(f"{API}/groups/{group.pk}/members").json()
        assert history[0]["left_on"] == "2026-10-31"
        assert history[0]["is_active"] is False

    def test_archiving_a_group_removes_its_future_lessons(
        self, admin_client: APIClient, slot: ScheduleSlot
    ) -> None:
        group = slot.course.group
        response = admin_client.patch(
            f"{API}/groups/{group.pk}", {"is_archived": True}, format="json"
        )
        assert response.status_code == 200
        assert not Lesson.objects.filter(date__gte=TODAY).exists()
        assert admin_client.get(f"{API}/groups").json() == []
        assert len(admin_client.get(f"{API}/groups", {"archived": "true"}).json()) == 1


@pytest.mark.django_db
class TestCourses:
    def test_teacher_must_be_a_teacher(
        self, admin_client: APIClient, group: Group, math: Subject, student: User, teacher: User
    ) -> None:
        url = f"{API}/courses"
        bad = {"group": str(group.pk), "subject": str(math.pk), "teacher": str(student.pk)}
        assert admin_client.post(url, bad, format="json").status_code == 400
        same = {**bad, "teacher": str(teacher.pk), "assistants": [str(teacher.pk)]}
        assert admin_client.post(url, same, format="json").json() == {
            "assistants": ["teacher_is_assistant"]
        }
        ok = {**bad, "teacher": str(teacher.pk)}
        assert admin_client.post(url, ok, format="json").status_code == 201
        assert admin_client.post(url, ok, format="json").json() == {
            "non_field_errors": ["course_exists"]
        }

    def test_new_teacher_takes_future_lessons_but_not_substitutions(
        self, admin_client: APIClient, slot: ScheduleSlot, make_user: MakeUser
    ) -> None:
        substitute = make_user(Role.TEACHER)
        newcomer = make_user(Role.TEACHER)
        lessons = list(Lesson.objects.filter(slot=slot).order_by("date"))
        lessons[0].teacher = substitute
        lessons[0].save()
        response = admin_client.patch(
            f"{API}/courses/{slot.course_id}", {"teacher": str(newcomer.pk)}, format="json"
        )
        assert response.status_code == 200
        teachers = list(
            Lesson.objects.filter(slot=slot).order_by("date").values_list("teacher", flat=True)
        )
        assert teachers == [substitute.pk, newcomer.pk, newcomer.pk, newcomer.pk]

    def test_group_of_a_course_cannot_change(
        self, admin_client: APIClient, course: Course, other_group: Group
    ) -> None:
        response = admin_client.patch(
            f"{API}/courses/{course.pk}", {"group": str(other_group.pk)}, format="json"
        )
        assert response.json() == {"group": ["cannot_change_group"]}


@pytest.mark.django_db
class TestHolidays:
    def test_new_holiday_removes_generated_lessons_and_deleting_restores(
        self, admin_client: APIClient, slot: ScheduleSlot
    ) -> None:
        day = TODAY + timedelta(weeks=1)
        moved = Lesson.objects.get(slot=slot, date=TODAY + timedelta(weeks=2))
        response = admin_client.post(
            f"{API}/holidays", {"date": day.isoformat(), "name": "Праздник"}, format="json"
        )
        assert response.status_code == 201
        assert not Lesson.objects.filter(date=day).exists()
        assert Lesson.objects.filter(pk=moved.pk).exists()
        admin_client.delete(f"{API}/holidays/{response.json()['id']}")
        assert Lesson.objects.filter(date=day).count() == 1

    def test_exceptions_survive_a_new_holiday(
        self, admin_client: APIClient, slot: ScheduleSlot
    ) -> None:
        day = TODAY + timedelta(weeks=1)
        lesson = Lesson.objects.get(slot=slot, date=day)
        lesson.status = LessonStatus.CANCELLED
        lesson.cancel_reason = "x"
        lesson.save()
        admin_client.post(
            f"{API}/holidays", {"date": day.isoformat(), "name": "Праздник"}, format="json"
        )
        assert Lesson.objects.filter(pk=lesson.pk).exists()


@pytest.mark.django_db
def test_teacher_subjects_in_user_card(
    admin_client: APIClient, teacher: User, math: Subject
) -> None:
    response = admin_client.patch(
        f"/api/v1/admin/users/{teacher.pk}",
        {"teacher_profile": {"subjects": [str(math.pk)]}},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["teacher_profile"]["subjects"] == [str(math.pk)]
