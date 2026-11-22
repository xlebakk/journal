"""The parent role (SPEC §16.1, stage 14): the children's student pages, read-only."""

from collections.abc import Callable
from datetime import date, time, timedelta
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.academics.models import Course, Group, LessonType, WorkType
from apps.accounts.models import ParentLink, Role, User
from apps.announcements.models import Announcement, Audience
from apps.audit.models import AuditLog
from apps.journal.models import Grade
from apps.schedule.models import Lesson
from conftest import TODAY, MakeUser, enroll

ClientFor = Callable[..., APIClient]


def parents_url(student: User) -> str:
    return f"/api/v1/admin/users/{student.pk}/parents"


@pytest.fixture
def graded(course: Course, student: User, frozen_today: date) -> Grade:
    """Yesterday's lesson with an 88 for the student."""
    day = TODAY - timedelta(days=1)
    lesson = Lesson.objects.create(
        course=course, date=day, start_time=time(14), end_time=time(15, 30),
        teacher=course.teacher, lesson_type=LessonType.objects.get(short="Пр"),
        planned_date=day, planned_start_time=time(14), planned_end_time=time(15, 30),
        topic="Логарифмы",
    )  # fmt: skip
    work = WorkType.objects.get(name="Ответ на занятии")
    return Grade.objects.create(
        lesson=lesson, student=student, value=88, scale="100", work_type=work,
        weight=work.weight, position=1, created_by=course.teacher,
    )  # fmt: skip


@pytest.mark.django_db
class TestAdminLinks:
    def test_new_parent_from_the_student_card(self, student: User, admin_client: APIClient) -> None:
        response = admin_client.post(
            parents_url(student),
            {
                "last_name": "Алиева",
                "first_name": "Гульнора",
                "middle_name": "",
                "password": "мамин пароль для журнала",
            },
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        parent = User.objects.get(pk=body["parent"]["id"])
        assert (parent.roles, parent.must_change_password) == (["parent"], False)
        assert parent.check_password("мамин пароль для журнала")
        assert ParentLink.objects.filter(parent=parent, student=student).exists()
        actions = set(AuditLog.objects.values_list("action", flat=True))
        assert {"user.create", "parent.link"} <= actions
        listed = admin_client.get(parents_url(student)).json()
        assert [p["full_name"] for p in listed] == [parent.full_name]

    def test_existing_parent_for_a_sibling_and_unlink(
        self, student: User, make_user: MakeUser, admin_client: APIClient
    ) -> None:
        parent = make_user(Role.PARENT)
        sibling = make_user(Role.STUDENT)
        for child in (student, sibling):
            response = admin_client.post(
                parents_url(child), {"existing": str(parent.pk)}, format="json"
            )
            assert response.status_code == 201
        again = admin_client.post(parents_url(student), {"existing": str(parent.pk)}, format="json")
        assert again.json() == {"existing": ["already_linked"]}
        children = admin_client.get(f"/api/v1/admin/users/{parent.pk}/children").json()
        assert len(children) == 2
        gone = admin_client.delete(f"{parents_url(student)}/{parent.pk}")
        assert gone.status_code == 204
        assert AuditLog.objects.filter(action="parent.unlink").exists()

    def test_only_parents_link_and_only_to_students(
        self, student: User, teacher: User, make_user: MakeUser, admin_client: APIClient
    ) -> None:
        not_parent = admin_client.post(
            parents_url(student), {"existing": str(teacher.pk)}, format="json"
        )
        assert not_parent.status_code == 404
        parent = make_user(Role.PARENT)
        to_teacher = admin_client.post(
            parents_url(teacher), {"existing": str(parent.pk)}, format="json"
        )
        assert to_teacher.status_code == 404
        assert admin_client.post(parents_url(student), {}, format="json").status_code == 400

    def test_teachers_students_and_parents_cannot_link(
        self, student: User, teacher: User, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        parent = make_user(Role.PARENT)
        for user in (teacher, student, parent):
            response = client_for(user).post(
                parents_url(student), {"existing": str(parent.pk)}, format="json"
            )
            assert response.status_code == 403


@pytest.mark.django_db
class TestParentPages:
    def link(self, parent: User, *children: User) -> None:
        for child in children:
            ParentLink.objects.create(parent=parent, student=child)

    def test_parent_reads_the_childs_pages(
        self, student: User, graded: Grade, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        parent = make_user(Role.PARENT)
        self.link(parent, student)
        client = client_for(parent)
        children = client.get("/api/v1/parent/children").json()
        assert [(c["full_name"], c["groups"]) for c in children] == [
            (student.full_name, ["11-М вечерняя"])
        ]
        child = {"child": str(student.pk)}
        grades = client.get("/api/v1/student/grades", child).json()
        assert [g["value"] for c in grades["courses"] for g in c["grades"]] == [88]
        for path in ("home", "diary", "attendance", "exams", "profile", "payments"):
            assert client.get(f"/api/v1/student/{path}", child).status_code == 200, path
        week = {"from": str(TODAY - timedelta(days=7)), "to": str(TODAY), **child}
        assert client.get("/api/v1/student/schedule", week).status_code == 200
        # Without ?child= the first child; the same data.
        assert client.get("/api/v1/student/grades").json() == grades

    def test_someone_elses_child_is_404(
        self, student: User, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        parent = make_user(Role.PARENT)
        stranger = make_user(Role.STUDENT)
        self.link(parent, stranger)
        client = client_for(parent)
        response = client.get("/api/v1/student/grades", {"child": str(student.pk)})
        assert response.status_code == 404
        assert client.get("/api/v1/student/grades", {"child": "garbage"}).status_code == 400
        lonely = client_for(make_user(Role.PARENT))
        assert lonely.get("/api/v1/student/grades").status_code == 404
        assert lonely.get("/api/v1/parent/children").json() == []

    def test_read_only_and_no_other_sections(
        self, student: User, graded: Grade, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        parent = make_user(Role.PARENT)
        self.link(parent, student)
        client = client_for(parent)
        assert client.get("/api/v1/journal/courses").status_code == 403
        assert client.get("/api/v1/admin/users").status_code == 403
        assert client.get("/api/v1/teacher/today").status_code == 403
        assert client.get("/api/v1/me/calendar").status_code == 403
        write = client.post(
            f"/api/v1/journal/lessons/{graded.lesson_id}/grades",
            {"student": str(student.pk), "value": 100},
            format="json",
        )
        assert write.status_code == 403
        # A student does not see the parent's list.
        assert client_for(student).get("/api/v1/parent/children").status_code == 403

    def test_announcements_of_the_childs_groups(
        self,
        student: User,
        group: Group,
        other_group: Group,
        admin: User,
        make_user: MakeUser,
        client_for: ClientFor,
    ) -> None:
        enroll(group, student)
        parent = make_user(Role.PARENT)
        self.link(parent, student)

        def post(title: str, **fields: Any) -> None:
            item = Announcement.objects.create(author=admin, title=title, body="…", **fields)
            if "groups" in title:
                item.groups.set([group if title == "groups mine" else other_group])

        post("all", audience=Audience.ALL)
        post("students", audience=Audience.ROLE, role="student")
        post("teachers", audience=Audience.ROLE, role="teacher")
        post("groups mine", audience=Audience.GROUPS)
        post("groups other", audience=Audience.GROUPS)
        titles = {a["title"] for a in client_for(parent).get("/api/v1/announcements").json()}
        assert titles == {"all", "students", "groups mine"}
