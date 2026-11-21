"""Student import and access cards (SPEC §8.2, §15: «импорт учеников администратором»)."""

import io
from collections.abc import Callable
from typing import Any

import pytest
from django.contrib.auth.hashers import check_password
from openpyxl import Workbook, load_workbook
from rest_framework.test import APIClient

from apps.academics.models import GroupMembership
from apps.accounts.credentials import TEMP_PASSWORD_LENGTH
from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from conftest import MakeUser

ClientFor = Callable[..., APIClient]
URL = "/api/v1/admin/import/students"
HEADER = "Фамилия*;Имя*;Отчество;Логин;Группа;Дата зачисления;Класс;Телефон родителя"


def upload(text: str, name: str = "students.csv", encoding: str = "utf-8") -> io.BytesIO:
    data = io.BytesIO(text.encode(encoding))
    data.name = name
    return data


def send(client: APIClient, text: str, apply: bool = False, **kw: Any) -> Any:
    form: dict[str, Any] = {"file": upload(text, **kw)}
    if apply:
        form["apply"] = "true"
    return client.post(URL, form, format="multipart")


@pytest.mark.django_db
class TestStudentImport:
    def test_template(self, admin_client: APIClient) -> None:
        response = admin_client.get(f"{URL}/template")
        book = load_workbook(io.BytesIO(response.content))
        assert book.sheetnames == ["Ученики", "Пример"]
        assert book["Ученики"]["A1"].value == "Фамилия*"

    def test_preview_errors_per_line_and_nothing_written(
        self, admin_client: APIClient, group: Any, make_user: MakeUser
    ) -> None:
        make_user(Role.STUDENT, login="taken.login")
        text = "\n".join(
            [
                HEADER,
                "Алиев;Фарход;;;11-М вечерняя;01.09.2026;11;+998 90 000 00 00",
                ";Нет фамилии;;;;;;",
                "Бобоев;Али;;taken.login;;;;",
                "Валиев;Рустам;;;Нет такой;;;",
                "Ганиев;Олим;;;;31.02.2026;12;abc",
                "Даминов;Иса;;same;;;;",
                "Ергашев;Тимур;;same;;;;",
            ]
        )
        body = send(admin_client, text).json()
        assert body["applied"] is False
        assert [r["issues"] for r in body["rows"]] == [
            [],
            ["last_name:required"],
            ["login:login_taken"],
            ["group:group_not_found"],
            ["joined_on:invalid_date", "school_grade:invalid_choice", "parent_phone:invalid_phone"],
            ["login:duplicate_in_file"],
            ["login:duplicate_in_file"],
        ]
        assert body["rows"][0]["group_name"] == "11-М вечерняя"
        assert send(admin_client, text, apply=True).json()["applied"] is False
        assert not User.objects.filter(last_name="Алиев").exists()

    def test_apply_creates_students_logins_passwords_and_memberships(
        self, admin_client: APIClient, group: Any
    ) -> None:
        text = "\n".join(
            [
                HEADER,
                "Алиев;Фарход;Рустамович;;11-м вечерняя;01.09.2026;11;",
                "Алиев;Фуркат;;;;;;",
                "Ганиева;Мадина;;aliev.f;;;;",
            ]
        )
        body = send(admin_client, text, apply=True, encoding="cp1251").json()
        assert body["applied"] is True, body
        created = body["created"]
        # The explicit login is honoured; generated ones go around it.
        assert [c["login"] for c in created] == ["aliev.f2", "aliev.f3", "aliev.f"]
        assert all(len(c["temporary_password"]) == TEMP_PASSWORD_LENGTH for c in created)
        first = User.objects.get(login="aliev.f2")
        assert first.must_change_password
        assert first.roles == [Role.STUDENT]
        assert check_password(created[0]["temporary_password"], first.password)
        assert first.student_profile.school_grade == 11
        membership = GroupMembership.objects.get(student=first)
        assert (membership.group_id, str(membership.joined_on)) == (group.pk, "2026-09-01")
        assert AuditLog.objects.filter(action="user.create").count() == 3

    def test_xlsx_and_duplicate_warning(self, admin_client: APIClient, make_user: MakeUser) -> None:
        make_user(Role.STUDENT, last_name="Алиев", first_name="Фарход")
        book = Workbook()
        sheet = book.worksheets[0]
        sheet.append(["Фамилия*", "Имя*"])
        sheet.append(["Алиев", "Фарход"])
        data = io.BytesIO()
        book.save(data)
        data.seek(0)
        data.name = "s.xlsx"
        body = admin_client.post(URL, {"file": data}, format="multipart").json()
        assert body["rows"][0]["warnings"] == ["possible_duplicate"]
        assert body["rows"][0]["issues"] == []

    def test_files_are_checked(self, admin_client: APIClient, settings: Any) -> None:
        assert admin_client.post(URL, {}, format="multipart").json() == {"file": ["required"]}
        binary = io.BytesIO(b"\x00\x01\x02 not a table")
        binary.name = "x.csv"
        response = admin_client.post(URL, {"file": binary}, format="multipart")
        assert response.json() == {"file": ["unsupported_file"]}
        settings.IMPORT_MAX_BYTES = 10
        response = send(admin_client, HEADER + "\nАлиев;Фарход")
        assert response.json() == {"file": ["file_too_large"]}

    def test_teacher_cannot_import(self, teacher: User, client_for: ClientFor) -> None:
        assert send(client_for(teacher), HEADER).status_code == 403


@pytest.mark.django_db
def test_access_card_info_has_qr(admin_client: APIClient) -> None:
    body = admin_client.get("/api/v1/admin/access-cards").json()
    assert body["site_url"].startswith("https://")
    assert body["qr"].startswith("data:image/svg+xml;base64,")
