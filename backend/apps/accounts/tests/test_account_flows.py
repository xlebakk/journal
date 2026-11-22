"""Temporary password, 2FA, session timeouts and revocation, role switch, re-auth."""

import time
from collections.abc import Callable
from datetime import timedelta

import pyotp
import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import sessions
from apps.accounts.models import BackupCode, Role, User, UserSession
from apps.audit.models import AuditLog
from conftest import PASSWORD, MakeUser, api_login, totp_code

ClientFor = Callable[..., APIClient]
NEW_PASSWORD = "quiet-silver-mountain-77"


def change_password(client: APIClient, current: str, new: str) -> object:
    return client.post(
        "/api/v1/auth/password",
        {"current_password": current, "new_password": new},
        format="json",
    )


@pytest.mark.django_db
class TestTemporaryPassword:
    def test_only_password_change_is_allowed(self, make_user: MakeUser) -> None:
        user = make_user(Role.TEACHER, must_change_password=True)
        client = APIClient()
        api_login(client, user)
        assert client.get("/api/v1/me").json()["must_change_password"] is True
        response = client.get("/api/v1/auth/sessions")
        assert response.status_code == 403
        assert response.json() == {"detail": "password_change_required"}

        assert change_password(client, PASSWORD, NEW_PASSWORD).status_code == 204  # type: ignore[attr-defined]
        assert client.get("/api/v1/auth/sessions").status_code == 200
        assert client.get("/api/v1/me").json()["must_change_password"] is False

    @pytest.mark.parametrize(
        ("new_password", "reason"),
        [
            ("short1", "too short"),
            ("password123", "common"),
            ("aliev.farkhod", "similar to login"),
        ],
    )
    def test_weak_passwords_are_rejected(
        self, make_user: MakeUser, new_password: str, reason: str
    ) -> None:
        user = make_user(Role.STUDENT, login="aliev.farkhod", must_change_password=True)
        client = APIClient()
        api_login(client, user)
        response = change_password(client, PASSWORD, new_password)
        assert response.status_code == 400, reason  # type: ignore[attr-defined]
        assert "new_password" in response.json()  # type: ignore[attr-defined]

    def test_passphrase_without_symbols_is_accepted(self, make_user: MakeUser) -> None:
        user = make_user(Role.STUDENT, must_change_password=True)
        client = APIClient()
        api_login(client, user)
        assert change_password(client, PASSWORD, "зелёный чай по утрам").status_code == 204  # type: ignore[attr-defined]

    def test_wrong_current_password(self, student: User, client_for: ClientFor) -> None:
        client = client_for(student)
        response = change_password(client, "not-my-password", NEW_PASSWORD)
        assert response.status_code == 400  # type: ignore[attr-defined]
        assert response.json() == {"current_password": ["invalid_password"]}  # type: ignore[attr-defined]

    def test_change_ends_other_sessions_and_is_audited(
        self, student: User, client_for: ClientFor
    ) -> None:
        phone = client_for(student, ip="10.0.0.5")
        laptop = client_for(student, ip="10.0.0.6")
        old_cookie = laptop.cookies[settings.SESSION_COOKIE_NAME].value
        assert change_password(laptop, PASSWORD, NEW_PASSWORD).status_code == 204  # type: ignore[attr-defined]
        assert phone.get("/api/v1/me").status_code == 401
        assert laptop.get("/api/v1/me").status_code == 200
        assert laptop.cookies[settings.SESSION_COOKIE_NAME].value != old_cookie
        assert AuditLog.objects.filter(
            action="auth.password_change", entity_id=str(student.pk)
        ).exists()
        assert api_login(APIClient(), student, password=NEW_PASSWORD).status_code == 200


@pytest.mark.django_db
class TestTotpLogin:
    def test_second_step_is_required(self, admin: User) -> None:
        client = APIClient()
        response = client.post(
            "/api/v1/auth/login", {"login": admin.login, "password": PASSWORD}, format="json"
        )
        assert response.json() == {"step": "totp"}
        # No session yet.
        assert client.get("/api/v1/me").status_code == 401
        assert (
            client.post("/api/v1/auth/totp", {"code": "000000"}, format="json").status_code == 400
        )
        response = client.post("/api/v1/auth/totp", {"code": totp_code(admin)}, format="json")
        assert response.json() == {"step": "done"}
        assert client.get("/api/v1/me").json()["active_role"] == "admin"

    def test_code_cannot_be_replayed(self, admin: User) -> None:
        first = APIClient()
        first.post(
            "/api/v1/auth/login", {"login": admin.login, "password": PASSWORD}, format="json"
        )
        code = totp_code(admin)
        assert first.post("/api/v1/auth/totp", {"code": code}, format="json").status_code == 200
        second = APIClient()
        second.post(
            "/api/v1/auth/login", {"login": admin.login, "password": PASSWORD}, format="json"
        )
        response = second.post("/api/v1/auth/totp", {"code": code}, format="json")
        assert response.status_code == 400

    def test_backup_code_works_once(self, admin: User) -> None:
        from apps.accounts import totp

        codes = totp.generate_backup_codes(admin)
        for expected in (200, 400):
            client = APIClient()
            client.post(
                "/api/v1/auth/login", {"login": admin.login, "password": PASSWORD}, format="json"
            )
            response = client.post("/api/v1/auth/totp", {"code": codes[0].upper()}, format="json")
            assert response.status_code == expected

    def test_too_many_wrong_codes(self, admin: User) -> None:
        client = APIClient()
        client.post(
            "/api/v1/auth/login", {"login": admin.login, "password": PASSWORD}, format="json"
        )
        for _ in range(settings.TOTP_MAX_ATTEMPTS - 1):
            assert (
                client.post("/api/v1/auth/totp", {"code": "111111"}, format="json").status_code
                == 400
            )
        response = client.post("/api/v1/auth/totp", {"code": "111111"}, format="json")
        assert response.status_code == 429
        # The pending login is gone: even the right code no longer works.
        response = client.post("/api/v1/auth/totp", {"code": totp_code(admin)}, format="json")
        assert response.json() == {"detail": "totp_session_expired"}


@pytest.mark.django_db
class TestTotpSetup:
    def test_admin_2fa_is_optional_by_default(
        self, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        admin = make_user(Role.ADMIN, totp_enabled=False)
        client = client_for(admin)
        assert client.get("/api/v1/me").json()["totp_setup_required"] is False
        assert client.get("/api/v1/admin/users").status_code == 200

    def test_center_can_require_2fa_for_admins(
        self, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        from apps.core.models import CenterSettings

        s = CenterSettings.load()
        s.require_admin_2fa = True
        s.save()
        admin = make_user(Role.ADMIN, totp_enabled=False)
        client = client_for(admin)
        assert client.get("/api/v1/me").json()["totp_setup_required"] is True
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 403
        assert response.json() == {"detail": "totp_setup_required"}

        setup = client.get("/api/v1/auth/totp/setup").json()
        assert setup["qr"].startswith("data:image/svg+xml;base64,")
        assert setup["otpauth_uri"].startswith("otpauth://totp/")
        wrong = client.post("/api/v1/auth/totp/setup", {"code": "123456"}, format="json")
        assert wrong.status_code == 400
        code = pyotp.TOTP(setup["secret"]).now()
        response = client.post("/api/v1/auth/totp/setup", {"code": code}, format="json")
        assert response.status_code == 200
        assert len(response.json()["backup_codes"]) == 10
        assert client.get("/api/v1/admin/users").status_code == 200

        admin.refresh_from_db()
        assert admin.totp_enabled
        assert setup["secret"] not in admin.totp_secret  # stored encrypted
        assert BackupCode.objects.filter(user=admin).count() == 10
        stored = list(BackupCode.objects.values_list("code_hash", flat=True))
        assert not set(response.json()["backup_codes"]) & set(stored)

    def test_admin_turns_2fa_off_unless_required(self, admin_client: APIClient) -> None:
        from apps.core.models import CenterSettings

        s = CenterSettings.load()
        s.require_admin_2fa = True
        s.save()
        response = admin_client.delete("/api/v1/auth/totp/setup")
        assert response.json() == {"detail": "totp_required"}
        s.require_admin_2fa = False
        s.save()
        assert admin_client.delete("/api/v1/auth/totp/setup").status_code == 204

    def test_teacher_2fa_is_optional(self, make_user: MakeUser, client_for: ClientFor) -> None:
        teacher = make_user(Role.TEACHER, totp_enabled=True)
        client = client_for(teacher)
        assert client.delete("/api/v1/auth/totp/setup").status_code == 204
        teacher.refresh_from_db()
        assert not teacher.totp_enabled

    def test_policy_can_require_2fa_for_teachers(
        self, teacher: User, client_for: ClientFor
    ) -> None:
        from apps.core.models import CenterSettings

        s = CenterSettings.load()
        s.require_teacher_2fa = True
        s.save()
        client = client_for(teacher)
        assert client.get("/api/v1/auth/sessions").json() == {"detail": "totp_setup_required"}


@pytest.mark.django_db
class TestSessionPolicy:
    def _age_session(self, client: APIClient, seconds: int) -> None:
        session = client.session
        session[sessions.LAST_SEEN] = time.time() - seconds
        session.save()

    def test_admin_idle_timeout(self, admin_client: APIClient) -> None:
        self._age_session(admin_client, 29 * 60)
        assert admin_client.get("/api/v1/me").status_code == 200
        self._age_session(admin_client, 31 * 60)
        assert admin_client.get("/api/v1/me").status_code == 401

    def test_teacher_idle_timeout_is_two_hours(self, teacher: User, client_for: ClientFor) -> None:
        client = client_for(teacher)
        self._age_session(client, 119 * 60)
        assert client.get("/api/v1/me").status_code == 200
        self._age_session(client, 121 * 60)
        assert client.get("/api/v1/me").status_code == 401

    def test_admin_and_teacher_gets_admin_limits_in_teacher_role(
        self, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        director = make_user(Role.ADMIN, Role.TEACHER)
        client = client_for(director)
        client.post("/api/v1/auth/role", {"role": "teacher"}, format="json")
        self._age_session(client, 31 * 60)
        assert client.get("/api/v1/me").status_code == 401

    def test_absolute_timeout(self, student: User, client_for: ClientFor) -> None:
        client = client_for(student)
        UserSession.objects.filter(user=student).update(expires_at=timezone.now())
        assert client.get("/api/v1/me").status_code == 401
        assert UserSession.objects.get(user=student).end_reason == "absolute_timeout"

    @pytest.mark.parametrize(
        ("roles", "remember", "max_age_days", "absolute_hours"),
        [
            ((Role.STUDENT,), False, None, 12),
            ((Role.STUDENT,), True, 30, 30 * 24),
            ((Role.TEACHER,), False, None, 12),
            ((Role.TEACHER,), True, 14, 14 * 24),
            ((Role.ADMIN,), True, None, 8),  # «remember» does not apply to admins
        ],
    )
    def test_cookie_lifetime_by_role(
        self,
        make_user: MakeUser,
        client_for: ClientFor,
        roles: tuple[str, ...],
        remember: bool,
        max_age_days: int | None,
        absolute_hours: int,
    ) -> None:
        user = make_user(*roles)
        client = client_for(user, remember=remember)
        cookie = client.cookies[settings.SESSION_COOKIE_NAME]
        if max_age_days is None:
            assert not cookie["max-age"]
        else:
            assert int(cookie["max-age"]) == max_age_days * 86400
        record = UserSession.objects.get(user=user)
        assert record.expires_at - record.created_at == pytest.approx(
            timedelta(hours=absolute_hours), abs=timedelta(seconds=5)
        )

    def test_blocked_user_is_logged_out_immediately(
        self, student: User, client_for: ClientFor
    ) -> None:
        client = client_for(student)
        User.objects.filter(pk=student.pk).update(is_active=False)
        assert client.get("/api/v1/me").status_code == 401


@pytest.mark.django_db
class TestOwnSessions:
    def test_list_and_revoke_other_device(self, student: User, client_for: ClientFor) -> None:
        phone = client_for(student, ip="10.0.0.1")
        laptop = client_for(student, ip="10.0.0.2")
        listed = laptop.get("/api/v1/auth/sessions").json()
        assert len(listed) == 2
        assert [s["current"] for s in listed].count(True) == 1
        other = next(s for s in listed if not s["current"])
        assert other["ip"] == "10.0.0.1"
        assert laptop.delete(f"/api/v1/auth/sessions/{other['id']}").status_code == 204
        assert phone.get("/api/v1/me").status_code == 401
        assert laptop.get("/api/v1/me").status_code == 200

    def test_cannot_revoke_someone_elses_session(
        self, student: User, teacher: User, client_for: ClientFor
    ) -> None:
        client_for(teacher)
        foreign = UserSession.objects.get(user=teacher)
        client = client_for(student)
        assert client.delete(f"/api/v1/auth/sessions/{foreign.pk}").status_code == 404
        foreign.refresh_from_db()
        assert foreign.ended_at is None

    def test_end_all_others(self, student: User, client_for: ClientFor) -> None:
        devices = [client_for(student, ip=f"10.0.0.{i}") for i in range(3)]
        response = devices[0].post("/api/v1/auth/sessions/end-others")
        assert response.json() == {"ended": 2}
        assert [d.get("/api/v1/me").status_code for d in devices] == [200, 401, 401]


@pytest.mark.django_db
class TestRoleSwitch:
    def test_switch_changes_access_and_session_id(
        self, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        director = make_user(Role.ADMIN, Role.TEACHER)
        client = client_for(director)
        assert client.get("/api/v1/me").json()["active_role"] == "admin"
        assert client.get("/api/v1/admin/users").status_code == 200
        before = client.cookies[settings.SESSION_COOKIE_NAME].value
        response = client.post("/api/v1/auth/role", {"role": "teacher"}, format="json")
        assert response.json()["active_role"] == "teacher"
        assert client.cookies[settings.SESSION_COOKIE_NAME].value != before
        assert client.get("/api/v1/admin/users").status_code == 403

    def test_cannot_switch_to_unassigned_role(self, student: User, client_for: ClientFor) -> None:
        client = client_for(student)
        response = client.post("/api/v1/auth/role", {"role": "admin"}, format="json")
        assert response.status_code == 400
        assert client.get("/api/v1/me").json()["active_role"] == "student"


@pytest.mark.django_db
class TestReauth:
    def test_wrong_password_counts_towards_lockout(
        self, student: User, client_for: ClientFor
    ) -> None:
        client = client_for(student)
        for _ in range(5):
            assert (
                client.post(
                    "/api/v1/auth/reauth", {"password": "nope-nope-nope"}, format="json"
                ).status_code
                == 400
            )
        response = client.post("/api/v1/auth/reauth", {"password": PASSWORD}, format="json")
        assert response.status_code == 429

    def test_reauth_refreshes_window(self, admin_client: APIClient) -> None:
        session = admin_client.session
        session[sessions.REAUTH_AT] = time.time() - 600
        session.save()
        assert (
            admin_client.post(
                "/api/v1/auth/reauth", {"password": PASSWORD}, format="json"
            ).status_code
            == 204
        )
        assert time.time() - admin_client.session[sessions.REAUTH_AT] < 5
