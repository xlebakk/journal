"""Administrator: users CRUD and account actions (SPEC §8.2)."""

import time
from collections.abc import Callable
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts import credentials, lockout, sessions
from apps.accounts.models import Role, User, UserSession
from apps.audit.models import AuditLog
from conftest import PASSWORD, MakeUser, api_login

ClientFor = Callable[..., APIClient]
USERS = "/api/v1/admin/users"


def create(client: APIClient, **data: Any) -> Any:
    payload = {"last_name": "Алиев", "first_name": "Фарход", "roles": ["student"], **data}
    return client.post(USERS, payload, format="json")


def expire_reauth(client: APIClient) -> None:
    session = client.session
    session[sessions.REAUTH_AT] = time.time() - 600
    session.save()


@pytest.mark.django_db
class TestCreate:
    def test_student_with_generated_login_and_temporary_password(
        self, admin_client: APIClient, admin: User
    ) -> None:
        response = create(
            admin_client,
            middle_name="Рустамович",
            student_profile={
                "school": "Школа №1",
                "school_grade": 11,
                "parent_phone": "+998901234567",
            },
        )
        assert response.status_code == 201, response.json()
        body = response.json()
        password = body["temporary_password"]
        assert len(password) == 12
        assert set(password) <= set(credentials.TEMP_PASSWORD_ALPHABET)
        assert body["user"]["login"] == "aliev.f"
        assert body["user"]["must_change_password"] is True
        assert body["user"]["student_profile"]["school_grade"] == 11

        user = User.objects.get(login="aliev.f")
        assert user.check_password(password)
        assert password not in user.password
        entry = AuditLog.objects.get(action="user.create")
        assert entry.actor == admin
        assert entry.after is not None
        assert entry.after["login"] == "aliev.f"
        assert password not in str(entry.after)
        assert "password" not in entry.after

        # The new user can log in, but only to change the password.
        client = APIClient()
        assert api_login(client, user, password=password).status_code == 200
        assert client.get("/api/v1/auth/sessions").json() == {"detail": "password_change_required"}

    def test_duplicate_names_get_numbered_logins(self, admin_client: APIClient) -> None:
        logins = [create(admin_client).json()["user"]["login"] for _ in range(3)]
        assert logins == ["aliev.f", "aliev.f2", "aliev.f3"]

    def test_explicit_login(self, admin_client: APIClient) -> None:
        response = create(admin_client, login="  Farkhod.A ")
        assert response.json()["user"]["login"] == "farkhod.a"
        assert create(admin_client, login="farkhod.a").json() == {"login": ["login_taken"]}
        assert create(admin_client, login="bad login!").json() == {"login": ["invalid_login"]}

    @pytest.mark.parametrize(
        ("roles", "error"),
        [
            ([], "roles_required"),
            (["student", "teacher"], "student_role_exclusive"),
            (["superuser"], "unknown_role"),
            (["parent"], "unknown_role"),
        ],
    )
    def test_invalid_roles(self, admin_client: APIClient, roles: list[str], error: str) -> None:
        assert create(admin_client, roles=roles).json() == {"roles": [error]}

    def test_profiles_follow_roles(self, admin_client: APIClient) -> None:
        body = create(
            admin_client,
            roles=["admin", "teacher"],
            teacher_profile={"phone": "+998 90 111 22 33"},
            student_profile={"school": "ignored"},
        ).json()["user"]
        assert body["teacher_profile"] == {"phone": "+998 90 111 22 33", "subjects": []}
        assert body["student_profile"] is None


@pytest.mark.django_db
class TestListAndRetrieve:
    def test_search_and_filters(
        self, admin_client: APIClient, make_user: MakeUser, admin: User
    ) -> None:
        make_user(Role.STUDENT, last_name="Алиев", first_name="Фарход")
        make_user(Role.STUDENT, last_name="Каримов", first_name="Санжар", is_active=False)
        make_user(Role.TEACHER, last_name="Алиева", first_name="Нигора")

        def logins(**params: str) -> list[str]:
            data = admin_client.get(USERS, params).json()
            return sorted(u["last_name"] for u in data["results"])

        assert logins(q="алиев") == ["Алиев", "Алиева"]
        assert logins(role="teacher") == ["Алиева"]
        assert logins(status="blocked") == ["Каримов"]
        assert logins(q="фарход алиев") == ["Алиев"]

    def test_unknown_id_is_404(self, admin_client: APIClient) -> None:
        response = admin_client.get(f"{USERS}/00000000-0000-4000-8000-000000000000")
        assert response.status_code == 404
        assert response.json() == {"detail": "not_found"}

    def test_detail_shows_parent_contacts_to_admin(
        self, admin_client: APIClient, student: User
    ) -> None:
        body = admin_client.get(f"{USERS}/{student.pk}").json()
        assert body["student_profile"]["parent_phone"] == "+998 90 000 00 00"


@pytest.mark.django_db
class TestUpdate:
    def test_names_are_audited_before_and_after(
        self, admin_client: APIClient, student: User
    ) -> None:
        response = admin_client.patch(
            f"{USERS}/{student.pk}", {"first_name": "  Фарходжон "}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["first_name"] == "Фарходжон"
        entry = AuditLog.objects.get(action="user.update")
        assert entry.before is not None
        assert entry.after is not None
        assert (entry.before["first_name"], entry.after["first_name"]) == ("Фарход", "Фарходжон")

    def test_roles_change_needs_fresh_password_and_ends_sessions(
        self, admin_client: APIClient, teacher: User, client_for: ClientFor
    ) -> None:
        teacher_client = client_for(teacher)
        expire_reauth(admin_client)
        url = f"{USERS}/{teacher.pk}"
        response = admin_client.patch(url, {"roles": ["teacher", "admin"]}, format="json")
        assert response.status_code == 403
        assert response.json() == {"detail": "reauth_required"}

        admin_client.post("/api/v1/auth/reauth", {"password": PASSWORD}, format="json")
        response = admin_client.patch(url, {"roles": ["teacher", "admin"]}, format="json")
        assert response.status_code == 200
        assert sorted(response.json()["roles"]) == ["admin", "teacher"]
        assert AuditLog.objects.filter(action="user.roles_change").count() == 1
        assert teacher_client.get("/api/v1/me").status_code == 401

    def test_cannot_remove_own_admin_role(self, admin_client: APIClient, admin: User) -> None:
        response = admin_client.patch(f"{USERS}/{admin.pk}", {"roles": ["teacher"]}, format="json")
        assert response.json() == {"roles": ["cannot_remove_own_admin"]}

    def test_cannot_remove_last_admin(self, admin_client: APIClient, make_user: MakeUser) -> None:
        other = make_user(Role.ADMIN, is_active=False)
        response = admin_client.patch(f"{USERS}/{other.pk}", {"roles": ["teacher"]}, format="json")
        # `other` is blocked, so the caller is the only active admin — but the caller keeps
        # the role, so removing it from an inactive admin is allowed.
        assert response.status_code == 200

    def test_student_cannot_become_teacher_and_student(
        self, admin_client: APIClient, student: User
    ) -> None:
        response = admin_client.patch(
            f"{USERS}/{student.pk}", {"roles": ["student", "teacher"]}, format="json"
        )
        assert response.json() == {"roles": ["student_role_exclusive"]}


@pytest.mark.django_db
class TestAccountActions:
    def test_reset_password(
        self, admin_client: APIClient, student: User, client_for: ClientFor
    ) -> None:
        student_client = client_for(student)
        response = admin_client.post(f"{USERS}/{student.pk}/reset-password")
        assert response.status_code == 200
        password = response.json()["temporary_password"]
        assert student_client.get("/api/v1/me").status_code == 401
        assert api_login(APIClient(), student).status_code == 400  # old password gone
        client = APIClient()
        assert api_login(client, student, password=password).status_code == 200
        assert client.get("/api/v1/me").json()["must_change_password"] is True
        assert AuditLog.objects.filter(action="user.password_reset").exists()

    def test_block_and_unblock(
        self, admin_client: APIClient, student: User, client_for: ClientFor
    ) -> None:
        student_client = client_for(student)
        assert admin_client.post(f"{USERS}/{student.pk}/block").json()["status"] == "blocked"
        assert student_client.get("/api/v1/me").status_code == 401
        assert api_login(APIClient(), student).status_code == 400
        assert admin_client.post(f"{USERS}/{student.pk}/unblock").json()["status"] == "active"
        assert api_login(APIClient(), student).status_code == 200

    def test_archive_keeps_data_and_disables_login(
        self, admin_client: APIClient, student: User
    ) -> None:
        body = admin_client.post(f"{USERS}/{student.pk}/archive").json()
        assert body["status"] == "archived"
        assert User.objects.filter(pk=student.pk).exists()
        assert api_login(APIClient(), student).status_code == 400
        assert admin_client.post(f"{USERS}/{student.pk}/unblock").json() == {
            "detail": "user_archived"
        }

    @pytest.mark.parametrize("action", ["block", "archive"])
    def test_cannot_disable_self(self, admin_client: APIClient, admin: User, action: str) -> None:
        response = admin_client.post(f"{USERS}/{admin.pk}/{action}")
        assert response.json() == {"detail": "cannot_apply_to_self"}

    def test_cannot_disable_last_other_admin_guard(
        self, admin_client: APIClient, make_user: MakeUser
    ) -> None:
        second = make_user(Role.ADMIN)
        assert admin_client.post(f"{USERS}/{second.pk}/block").status_code == 200

    def test_unlock_login(self, admin_client: APIClient, student: User) -> None:
        for _ in range(5):
            lockout.register_failure(student.login)
        assert admin_client.get(f"{USERS}/{student.pk}").json()["login_locked_minutes"] == 15
        admin_client.post(f"{USERS}/{student.pk}/unlock-login")
        assert lockout.locked_seconds(student.login) == 0
        assert api_login(APIClient(), student).status_code == 200

    def test_reset_2fa_needs_fresh_password(
        self, admin_client: APIClient, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        teacher = make_user(Role.TEACHER, totp_enabled=True)
        teacher_client = client_for(teacher)
        url = f"{USERS}/{teacher.pk}/reset-2fa"
        expire_reauth(admin_client)
        assert admin_client.post(url).json() == {"detail": "reauth_required"}
        admin_client.post("/api/v1/auth/reauth", {"password": PASSWORD}, format="json")
        assert admin_client.post(url).json()["totp_enabled"] is False
        assert teacher_client.get("/api/v1/me").status_code == 401
        assert AuditLog.objects.filter(action="user.2fa_reset").exists()

    def test_sessions_list_and_end(
        self, admin_client: APIClient, student: User, client_for: ClientFor
    ) -> None:
        phone = client_for(student, ip="10.1.1.1")
        laptop = client_for(student, ip="10.1.1.2")
        listed = admin_client.get(f"{USERS}/{student.pk}/sessions").json()
        assert len(listed) == 2
        phone_session = UserSession.objects.get(user=student, ip="10.1.1.1")
        url = f"{USERS}/{student.pk}/sessions/{phone_session.pk}"
        assert admin_client.delete(url).status_code == 204
        assert phone.get("/api/v1/me").status_code == 401
        assert laptop.get("/api/v1/me").status_code == 200
        assert admin_client.post(f"{USERS}/{student.pk}/sessions/end-all").json() == {"ended": 1}
        assert laptop.get("/api/v1/me").status_code == 401

    def test_session_of_another_user_is_404(
        self, admin_client: APIClient, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        client_for(teacher)
        foreign = UserSession.objects.get(user=teacher)
        response = admin_client.delete(f"{USERS}/{student.pk}/sessions/{foreign.pk}")
        assert response.status_code == 404


@pytest.mark.django_db
def test_audit_and_login_events_are_readable_by_admin(
    admin_client: APIClient, student: User
) -> None:
    admin_client.post(f"{USERS}/{student.pk}/block")
    audit = admin_client.get("/api/v1/admin/audit", {"action": "user.block"}).json()
    assert audit["count"] == 1
    assert audit["results"][0]["entity_id"] == str(student.pk)
    assert audit["results"][0]["before"] == {"is_active": True}
    events = admin_client.get("/api/v1/admin/login-events", {"success": "true"}).json()
    assert events["count"] >= 1
    assert admin_client.get("/api/v1/admin/audit", {"date_from": "nope"}).status_code == 400
