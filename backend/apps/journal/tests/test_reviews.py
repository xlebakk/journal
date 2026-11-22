"""Teacher reviews once per term (SPEC §16.5, stage 9)."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.academics.models import Course, Term
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from apps.journal.models import TeacherReview
from conftest import TODAY, MakeUser, enroll

ClientFor = Callable[..., APIClient]


@pytest.fixture
def terms(year: Any, frozen_today: date) -> dict[str, Term]:
    """Module 1 is long over, module 2 is current (TODAY = 2026-11-16), module 3 is ahead."""
    return {
        "past": Term.objects.create(
            year=year, name="Модуль 1", starts_on=date(2026, 9, 1), ends_on=date(2026, 10, 31)
        ),
        "current": Term.objects.create(
            year=year, name="Модуль 2", starts_on=date(2026, 11, 1), ends_on=date(2026, 12, 31)
        ),
        "future": Term.objects.create(
            year=year, name="Модуль 3", starts_on=date(2027, 1, 1), ends_on=date(2027, 3, 15)
        ),
    }


def url(course: Course, student: User | None = None) -> str:
    base = f"/api/v1/journal/courses/{course.pk}/reviews"
    return f"{base}/{student.pk}" if student else base


def put(client: APIClient, course: Course, student: User, term: Term, **body: Any) -> Any:
    return client.put(url(course, student), {"term": str(term.pk), **body}, format="json")


@pytest.mark.django_db
class TestWriting:
    def test_teacher_writes_updates_and_deletes(
        self,
        course: Course,
        student: User,
        teacher: User,
        terms: dict[str, Term],
        client_for: ClientFor,
    ) -> None:
        client = client_for(teacher)
        body = client.get(url(course)).json()
        assert body["term"]["name"] == "Модуль 2"  # the current one by default
        assert body["editable"] is True
        assert [r["full_name"] for r in body["rows"]] == [student.full_name]

        row = put(client, course, student, terms["current"], text="  Сильная алгебра.  ").json()
        assert (row["text"], row["version"]) == ("Сильная алгебра.", 1)
        stale = put(client, course, student, terms["current"], text="x", version=None)
        assert stale.status_code == 409
        row = put(client, course, student, terms["current"], text="Нужна геометрия.", version=1)
        assert row.json()["version"] == 2
        gone = put(client, course, student, terms["current"], text=" ", version=2).json()
        assert gone["text"] == ""
        assert not TeacherReview.objects.exists()
        actions = list(
            AuditLog.objects.filter(action__startswith="review.")
            .order_by("id")
            .values_list("action", flat=True)
        )
        assert actions == ["review.create", "review.update", "review.delete"]

    def test_assistant_reads_but_does_not_write(
        self,
        course: Course,
        student: User,
        make_user: MakeUser,
        terms: dict[str, Term],
        client_for: ClientFor,
    ) -> None:
        helper = make_user(Role.TEACHER)
        course.assistants.add(helper)
        client = client_for(helper)
        body = client.get(url(course)).json()
        assert (body["editable"], body["locked"]) == (False, "not_course_teacher")
        response = put(client, course, student, terms["current"], text="Отзыв")
        assert response.json() == {"detail": "not_course_teacher"}

    def test_foreign_teacher_and_student_get_nothing(
        self,
        course: Course,
        student: User,
        make_user: MakeUser,
        terms: dict[str, Term],
        client_for: ClientFor,
    ) -> None:
        assert client_for(make_user(Role.TEACHER)).get(url(course)).status_code == 404
        assert client_for(student).get(url(course)).status_code == 403

    def test_rules(
        self,
        course: Course,
        student: User,
        teacher: User,
        make_user: MakeUser,
        terms: dict[str, Term],
        client_for: ClientFor,
    ) -> None:
        client = client_for(teacher)
        too_long = put(client, course, student, terms["current"], text="а" * 601)
        assert too_long.json() == {"text": ["too_long"]}
        stranger = make_user(Role.STUDENT)
        assert put(client, course, stranger, terms["current"], text="x").json() == {
            "detail": ["student_not_in_group"]
        }
        assert put(client, course, student, terms["future"], text="x").json() == {
            "detail": ["term_not_started"]
        }
        left = make_user(Role.STUDENT)
        enroll(course.group, left, joined=date(2026, 9, 1), left=date(2026, 10, 15))
        # In the group during module 1, gone by module 2.
        current_rows = client.get(url(course), {"term": str(terms["current"].pk)}).json()["rows"]
        assert left.full_name not in [r["full_name"] for r in current_rows]

    def test_window_teacher_403_admin_with_reason(
        self,
        course: Course,
        student: User,
        teacher: User,
        admin: User,
        terms: dict[str, Term],
        client_for: ClientFor,
    ) -> None:
        past = terms["past"]  # ended 31.10, window closed on 07.11, today is 16.11
        response = put(client_for(teacher), course, student, past, text="Поздно")
        assert response.json() == {"detail": "edit_window_closed"}
        boss = client_for(admin)
        assert boss.get(url(course), {"term": str(past.pk)}).json()["needs_reason"] is True
        assert put(boss, course, student, past, text="Отзыв").json() == {
            "detail": ["reason_required"]
        }
        ok = put(boss, course, student, past, text="Отзыв", reason="забыли до каникул")
        assert ok.status_code == 200
        assert AuditLog.objects.get(action="review.create").reason == "забыли до каникул"

    def test_no_terms(
        self, course: Course, teacher: User, client_for: ClientFor, year: Any
    ) -> None:
        assert client_for(teacher).get(url(course)).json() == {"detail": ["no_terms"]}


@pytest.mark.django_db
def test_student_and_parents_see_the_review(
    course: Course,
    student: User,
    teacher: User,
    make_user: MakeUser,
    terms: dict[str, Term],
    admin_client: APIClient,
    client_for: ClientFor,
) -> None:
    classmate = make_user(Role.STUDENT)
    enroll(course.group, classmate)
    teacher_client = client_for(teacher)
    put(teacher_client, course, student, terms["current"], text="Хорошо решает задачи.")
    put(teacher_client, course, classmate, terms["current"], text="Чужой отзыв.")

    grades = (
        client_for(student).get("/api/v1/student/grades", {"term": str(terms["current"].pk)}).json()
    )
    assert [(r["subject_name"], r["term_name"], r["text"]) for r in grades["reviews"]] == [
        ("Математика", "Модуль 2", "Хорошо решает задачи.")
    ]
    summary = admin_client.get(
        f"/api/v1/admin/reports/students/{student.pk}",
        {"from": str(TODAY - timedelta(days=5)), "to": str(TODAY)},
    ).json()
    assert [r["text"] for r in summary["reviews"]] == ["Хорошо решает задачи."]
