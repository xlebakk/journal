"""Tokens of the Android app (stage 6)."""

import time
from collections.abc import Callable
from typing import Any

import pytest
from django.core import signing
from rest_framework.test import APIClient

from apps.accounts import sessions, tokens
from apps.accounts.models import LoginEvent, RefreshToken, Role, User, UserSession
from apps.audit.models import AuditLog
from conftest import PASSWORD, MakeUser, totp_code

ClientFor = Callable[..., APIClient]
A = "/api/v1/auth"


def app_login(user: User, password: str = PASSWORD) -> Any:
    return APIClient().post(
        f"{A}/token", {"login": user.login, "password": password}, format="json"
    )


def bearer(access: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def tokens_for(user: User) -> dict[str, Any]:
    response = app_login(user)
    assert response.status_code == 200, response.json()
    body: dict[str, Any] = response.json()
    if body["step"] == "totp":
        User.objects.filter(pk=user.pk).update(totp_last_counter=None)
        response = APIClient().post(
            f"{A}/token/totp", {"ticket": body["ticket"], "code": totp_code(user)}, format="json"
        )
        body = response.json()
    assert body["step"] == "done", body
    return body


def refresh(value: str) -> Any:
    return APIClient().post(f"{A}/token/refresh", {"refresh": value}, format="json")


@pytest.mark.django_db
class TestLogin:
    def test_tokens_without_cookies_and_bearer_works(self, student: User) -> None:
        response = app_login(student)
        body = response.json()
        assert body["step"] == "done"
        assert body["access_expires_in"] == 600
        assert "__Host-session" not in response.cookies
        me = bearer(body["access"]).get("/api/v1/me")
        assert me.status_code == 200
        assert me.json()["active_role"] == "student"
        session = UserSession.objects.get(user=student)
        assert session.kind == "app"
        # Only the hash of the refresh token is stored.
        assert not RefreshToken.objects.filter(token_hash=body["refresh"]).exists()
        assert LoginEvent.objects.filter(user=student, success=True).count() == 1

    def test_wrong_password_and_lockout_are_shared_with_the_site(self, student: User) -> None:
        assert app_login(student, "nope-nope-nope").json() == {"detail": "invalid_credentials"}
        for _ in range(5):
            app_login(student, "nope-nope-nope")
        assert app_login(student).status_code == 429

    def test_admin_second_step_with_a_one_time_ticket(self, admin: User) -> None:
        body = app_login(admin).json()
        assert body["step"] == "totp"
        client = APIClient()
        wrong = client.post(
            f"{A}/token/totp", {"ticket": body["ticket"], "code": "000000"}, format="json"
        )
        assert wrong.json() == {"detail": "invalid_code"}
        User.objects.filter(pk=admin.pk).update(totp_last_counter=None)
        ok = client.post(
            f"{A}/token/totp", {"ticket": body["ticket"], "code": totp_code(admin)}, format="json"
        )
        assert ok.json()["step"] == "done"
        again = client.post(
            f"{A}/token/totp", {"ticket": body["ticket"], "code": totp_code(admin)}, format="json"
        )
        assert again.json() == {"detail": "totp_session_expired"}
        forged = client.post(f"{A}/token/totp", {"ticket": "x", "code": "1"}, format="json")
        assert forged.json() == {"detail": "totp_session_expired"}

    def test_forged_or_expired_access_is_401(
        self, student: User, settings: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert bearer("garbage").get("/api/v1/me").status_code == 401
        body = tokens_for(student)
        real = time.time
        monkeypatch.setattr(signing.time, "time", lambda: real() + 601)  # type: ignore[attr-defined]
        response = bearer(body["access"]).get("/api/v1/me")
        assert response.status_code == 401
        assert response["WWW-Authenticate"].startswith("Bearer")

    def test_post_needs_no_csrf_with_a_token(self, make_user: MakeUser) -> None:
        both = make_user(Role.ADMIN, Role.TEACHER)
        client = bearer(tokens_for(both)["access"])
        response = client.post(f"{A}/role", {"role": "teacher"}, format="json")
        assert response.status_code == 200
        assert client.get("/api/v1/me").json()["active_role"] == "teacher"
        assert UserSession.objects.get(user=both).active_role == "teacher"
        assert client.get("/api/v1/admin/users").status_code == 403


@pytest.mark.django_db
class TestRefresh:
    def test_rotation_and_reuse_ends_the_chain(self, student: User) -> None:
        first = tokens_for(student)
        second = refresh(first["refresh"]).json()
        assert second["refresh"] != first["refresh"]
        assert bearer(second["access"]).get("/api/v1/me").status_code == 200
        # The spent token comes back: a copy exists somewhere, the whole session ends.
        assert refresh(first["refresh"]).json() == {"detail": "invalid_token"}
        session = UserSession.objects.get(user=student)
        assert session.end_reason == "token_reuse"
        assert bearer(second["access"]).get("/api/v1/me").status_code == 401
        assert refresh(second["refresh"]).status_code == 401

    def test_unknown_and_expired(self, student: User, settings: Any) -> None:
        assert refresh("nope").status_code == 401
        body = tokens_for(student)
        settings.APP_REFRESH_DAYS = 0
        RefreshToken.objects.update(expires_at=UserSession.objects.get().created_at)
        assert refresh(body["refresh"]).status_code == 401

    def test_refresh_is_thirty_days_for_every_role(self, admin: User) -> None:
        body = tokens_for(admin)
        session = UserSession.objects.get(user=admin, kind="app")
        days = (session.expires_at - session.created_at).days
        assert days in (29, 30)
        assert body["refresh_expires_at"]


@pytest.mark.django_db
class TestRevocation:
    def test_logout_ends_the_app_session(self, student: User) -> None:
        body = tokens_for(student)
        client = bearer(body["access"])
        assert client.post(f"{A}/logout").status_code == 204
        assert client.get("/api/v1/me").status_code == 401
        assert refresh(body["refresh"]).status_code == 401

    def test_block_and_session_list(
        self, student: User, admin_client: APIClient, client_for: ClientFor
    ) -> None:
        body = tokens_for(student)
        sessions_list = client_for(student).get(f"{A}/sessions").json()
        assert {s["kind"] for s in sessions_list} == {"web", "app"}
        admin_client.post(f"/api/v1/admin/users/{student.pk}/block", {}, format="json")
        assert bearer(body["access"]).get("/api/v1/me").status_code == 401
        assert refresh(body["refresh"]).status_code == 401

    def test_ending_the_app_session_from_the_site(
        self, student: User, client_for: ClientFor
    ) -> None:
        body = tokens_for(student)
        app = UserSession.objects.get(user=student, kind="app")
        web = client_for(student)
        assert web.delete(f"{A}/sessions/{app.pk}").status_code == 204
        assert bearer(body["access"]).get("/api/v1/me").status_code == 401

    def test_password_change_in_the_app_keeps_this_phone_only(
        self, student: User, client_for: ClientFor
    ) -> None:
        web = client_for(student)
        other = tokens_for(student)
        body = tokens_for(student)
        client = bearer(body["access"])
        response = client.post(
            f"{A}/password",
            {"current_password": PASSWORD, "new_password": "a-much-better-passphrase-77"},
            format="json",
        )
        assert response.status_code == 204, response.json()
        assert client.get("/api/v1/me").status_code == 200
        assert bearer(other["access"]).get("/api/v1/me").status_code == 401
        assert web.get("/api/v1/me").status_code == 401


@pytest.mark.django_db
class TestRulesStillApply:
    def test_forced_password_change(self, make_user: MakeUser) -> None:
        newbie = make_user(Role.STUDENT, must_change_password=True)
        client = bearer(tokens_for(newbie)["access"])
        assert client.get("/api/v1/student/home").json() == {"detail": "password_change_required"}
        assert client.get("/api/v1/me").status_code == 200

    def test_reauth_and_audit_role(self, admin: User, make_user: MakeUser) -> None:
        client = bearer(tokens_for(admin)["access"])
        session = UserSession.objects.get(user=admin, kind="app")
        teacher = make_user(Role.TEACHER, totp_enabled=True)
        url = f"/api/v1/admin/users/{teacher.pk}/reset-2fa"
        # Fresh login: a dangerous action passes without asking again.
        assert client.post(url, {}, format="json").status_code == 200
        sessions.AppState(session)[sessions.REAUTH_AT] = time.time() - 600
        assert client.post(url, {}, format="json").json() == {"detail": "reauth_required"}
        assert client.post(f"{A}/reauth", {"password": PASSWORD}, format="json").status_code == 204
        assert client.post(url, {}, format="json").status_code == 200
        log = AuditLog.objects.filter(action="user.2fa_reset").last()
        assert log is not None
        assert log.actor_role == "admin"

    def test_bearer_ignores_the_cookie(self, student: User, client_for: ClientFor) -> None:
        web = client_for(student)
        web.credentials(HTTP_AUTHORIZATION="Bearer forged")
        assert web.get("/api/v1/me").status_code == 401

    def test_ticket_is_signed_for_its_purpose(self, student: User) -> None:
        body = tokens_for(student)
        # An access token is not a 2FA ticket and the other way round.
        assert tokens.read_ticket(body["access"], 300) is None
        assert tokens.session_for_access(tokens.totp_ticket(student)) is None


@pytest.mark.django_db
class TestCors:
    def test_preflight_from_the_app(self) -> None:
        response = APIClient().options(
            "/api/v1/me",
            HTTP_ORIGIN="https://localhost",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
        )
        assert response.status_code == 204
        assert response["Access-Control-Allow-Origin"] == "https://localhost"
        assert "Authorization" in response["Access-Control-Allow-Headers"]
        assert "Access-Control-Allow-Credentials" not in response

    def test_other_origins_get_nothing(self, student: User) -> None:
        access = tokens_for(student)["access"]
        response = bearer(access).get("/api/v1/me", HTTP_ORIGIN="https://evil.example")
        assert "Access-Control-Allow-Origin" not in response
        ok = bearer(access).get("/api/v1/me", HTTP_ORIGIN="https://localhost")
        assert ok["Access-Control-Allow-Origin"] == "https://localhost"
