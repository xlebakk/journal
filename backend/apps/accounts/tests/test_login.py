"""Login, lockout and session cookie."""

from typing import Any

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts import lockout
from apps.accounts.models import LoginEvent, Role, User
from conftest import PASSWORD, MakeUser, api_login

LOGIN = "/api/v1/auth/login"


def post_login(client: APIClient, login: str, password: str, **extra: Any) -> Any:
    return client.post(LOGIN, {"login": login, "password": password, **extra}, format="json")


def comparable(response: Any) -> tuple[int, bytes, str | None, str | None]:
    """Everything an attacker could compare: status, body bytes, relevant headers."""
    return (
        response.status_code,
        response.content,
        response.headers.get("Content-Type"),
        response.headers.get("Retry-After"),
    )


@pytest.mark.django_db
class TestLogin:
    def test_login_opens_senior_role(self, make_user: MakeUser) -> None:
        user = make_user(Role.TEACHER, login="aliev.f")
        client = APIClient()
        assert api_login(client, user).data == {"step": "done"}
        me = client.get("/api/v1/me").json()
        assert me["roles"] == ["teacher"]
        assert me["active_role"] == "teacher"
        assert me["must_change_password"] is False

    def test_login_is_case_insensitive_and_trimmed(self, make_user: MakeUser) -> None:
        make_user(Role.STUDENT, login="aliev.f")
        response = post_login(APIClient(), "  ALIEV.F ", PASSWORD)
        assert response.status_code == 200
        assert response.data == {"step": "done"}

    def test_wrong_password_and_unknown_login_look_identical(self, student: User) -> None:
        wrong = post_login(APIClient(), student.login, "wrong-password-123")
        unknown = post_login(APIClient(), "no.such.user", "wrong-password-123")
        assert wrong.status_code == 400
        assert wrong.json() == {"detail": "invalid_credentials"}
        assert comparable(wrong) == comparable(unknown)

    @pytest.mark.parametrize("state", ["blocked", "archived"])
    def test_disabled_account_gets_the_same_error(self, student: User, state: str) -> None:
        from django.utils import timezone

        student.is_active = False
        if state == "archived":
            student.archived_at = timezone.now()
        student.save()
        response = post_login(APIClient(), student.login, PASSWORD)
        assert response.json() == {"detail": "invalid_credentials"}

    def test_events_are_logged_without_password(self, student: User) -> None:
        post_login(APIClient(), student.login, "wrong-password-123")
        post_login(APIClient(), student.login, PASSWORD)
        events = list(LoginEvent.objects.order_by("at").values("success", "reason", "user"))
        assert [(e["success"], e["reason"]) for e in events] == [
            (False, "invalid_credentials"),
            (True, "ok"),
        ]
        assert all(e["user"] == student.pk for e in events)
        stored = str(list(LoginEvent.objects.values()))
        assert "wrong-password-123" not in stored
        assert PASSWORD not in stored


@pytest.mark.django_db
class TestLockout:
    def test_sixth_attempt_is_429_and_identical_for_unknown_login(self, student: User) -> None:
        responses = {}
        for login in (student.login, "no.such.user"):
            client = APIClient(REMOTE_ADDR="10.0.0.1" if login == student.login else "10.0.0.2")
            for _ in range(5):
                assert post_login(client, login, "wrong-password-123").status_code == 400
            responses[login] = post_login(client, login, "wrong-password-123")
        locked = responses[student.login]
        assert locked.status_code == 429
        assert locked.json() == {"detail": "too_many_attempts", "retry_after_minutes": 15}
        assert locked.headers["Retry-After"] == "900"
        assert comparable(locked) == comparable(responses["no.such.user"])

    def test_correct_password_is_rejected_while_locked(self, student: User) -> None:
        client = APIClient()
        for _ in range(5):
            post_login(client, student.login, "wrong-password-123")
        assert post_login(client, student.login, PASSWORD).status_code == 429

    def test_lock_doubles_on_repeat_up_to_24_hours(self) -> None:
        durations = []
        for _ in range(9):
            for _attempt in range(4):
                assert lockout.register_failure("someone") == 0
            durations.append(lockout.register_failure("someone"))
        minutes = [d // 60 for d in durations]
        assert minutes == [15, 30, 60, 120, 240, 480, 960, 1440, 1440]

    def test_success_resets_failure_count(self, student: User) -> None:
        client = APIClient()
        for _ in range(4):
            post_login(client, student.login, "wrong-password-123")
        assert post_login(client, student.login, PASSWORD).status_code == 200
        for _ in range(4):
            assert post_login(APIClient(), student.login, "wrong").status_code == 400

    def test_ip_limit(self, student: User) -> None:
        client = APIClient(REMOTE_ADDR="10.9.9.9")
        for i in range(settings.LOGIN_IP_LIMIT):
            assert post_login(client, f"login{i}", "x").status_code == 400
        assert post_login(client, student.login, PASSWORD).status_code == 429
        # Another address is not affected.
        other = APIClient(REMOTE_ADDR="10.9.9.8")
        assert post_login(other, student.login, PASSWORD).status_code == 200


@pytest.mark.django_db
class TestCsrfAndCookies:
    def test_login_without_csrf_token_is_403(self, student: User) -> None:
        client = APIClient(enforce_csrf_checks=True)
        response = post_login(client, student.login, PASSWORD)
        assert response.status_code == 403

    def test_login_with_csrf_token_works(self, student: User) -> None:
        client = APIClient(enforce_csrf_checks=True)
        branding = client.get(LOGIN)
        assert branding.status_code == 200
        assert set(branding.json()) == {"center_name", "contacts", "logo"}
        token = client.cookies["__Host-csrftoken"].value
        response = client.post(
            LOGIN,
            {"login": student.login, "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        assert response.status_code == 200

    def test_authenticated_post_without_csrf_is_403(self, student: User) -> None:
        client = APIClient(enforce_csrf_checks=True)
        client.get(LOGIN)
        token = client.cookies["__Host-csrftoken"].value
        client.post(
            LOGIN, {"login": student.login, "password": PASSWORD}, format="json",
            HTTP_X_CSRFTOKEN=token,
        )  # fmt: skip
        assert client.post("/api/v1/auth/logout").status_code == 403
        # Login rotates the CSRF token: the old one no longer works.
        assert client.post("/api/v1/auth/logout", HTTP_X_CSRFTOKEN=token).status_code == 403
        fresh = client.cookies["__Host-csrftoken"].value
        assert fresh != token
        assert client.post("/api/v1/auth/logout", HTTP_X_CSRFTOKEN=fresh).status_code == 204

    def test_session_cookie_flags(self, student: User) -> None:
        client = APIClient()
        api_login(client, student)
        cookie = client.cookies[settings.SESSION_COOKIE_NAME]
        assert settings.SESSION_COOKIE_NAME == "__Host-session"
        assert cookie["httponly"]
        assert cookie["secure"]
        assert cookie["samesite"] == "Lax"
        assert cookie["path"] == "/"
        assert not cookie["domain"]

    def test_session_id_changes_on_login(self, student: User) -> None:
        client = APIClient()
        client.get(LOGIN)
        session = client.session
        session["probe"] = 1
        session.save()
        before = client.cookies[settings.SESSION_COOKIE_NAME].value
        api_login(client, student)
        assert client.cookies[settings.SESSION_COOKIE_NAME].value != before


@pytest.mark.django_db
class TestLogout:
    def test_logout_ends_session(self, student: User) -> None:
        client = APIClient()
        api_login(client, student)
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 204
        assert response.headers["Clear-Site-Data"] == '"cache"'
        assert client.get("/api/v1/me").status_code == 401
        assert student.sessions.get().end_reason == "logout"


@pytest.mark.django_db
def test_unknown_login_still_checks_a_password_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timing: without this, «no such user» would answer faster than «wrong password»."""
    from apps.accounts import views_auth

    checked: list[str] = []
    original = views_auth.check_password

    def spy(password: str, encoded: str) -> bool:
        checked.append(encoded)
        return original(password, encoded)

    monkeypatch.setattr(views_auth, "check_password", spy)
    post_login(APIClient(), "no.such.user", "some-password")
    assert checked == [views_auth._DUMMY_HASH]
    assert checked[0].startswith("argon2$")
