"""Shared fixtures. Tests log in through the real API, never by forcing a session."""

from collections.abc import Callable, Iterator
from typing import Any, Protocol

import pyotp
import pytest
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts import totp
from apps.accounts.models import Role, StudentProfile, TeacherProfile, User

PASSWORD = "bright-orange-river-42"


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Lockout counters and cached settings must not leak between tests."""
    cache.clear()
    yield
    cache.clear()


class MakeUser(Protocol):
    def __call__(
        self,
        *roles: str,
        login: str | None = None,
        password: str = PASSWORD,
        must_change_password: bool = False,
        totp_enabled: bool | None = None,
        **fields: Any,
    ) -> User: ...


_counter = 0


@pytest.fixture
def make_user(db: None) -> MakeUser:
    def factory(
        *roles: str,
        login: str | None = None,
        password: str = PASSWORD,
        must_change_password: bool = False,
        totp_enabled: bool | None = None,
        **fields: Any,
    ) -> User:
        global _counter
        _counter += 1
        roles = roles or (Role.STUDENT,)
        user = User.objects.create_user(
            login=login or f"user{_counter}",
            password=password,
            last_name=fields.pop("last_name", f"Фамилия{_counter}"),
            first_name=fields.pop("first_name", "Имя"),
            roles=list(roles),
            must_change_password=must_change_password,
            **fields,
        )
        if Role.STUDENT in roles:
            StudentProfile.objects.create(user=user, parent_phone="+998 90 000 00 00")
        if Role.TEACHER in roles:
            TeacherProfile.objects.create(user=user)
        # Administrators need 2FA; give it to them unless a test says otherwise.
        if totp_enabled if totp_enabled is not None else Role.ADMIN in roles:
            enable_totp(user)
        return user

    return factory


def enable_totp(user: User) -> str:
    secret = pyotp.random_base32()
    user.totp_secret = totp.encrypt_secret(secret)
    user.totp_enabled = True
    user.save(update_fields=["totp_secret", "totp_enabled"])
    user.test_totp_secret = secret  # type: ignore[attr-defined]
    return secret


def totp_code(user: User) -> str:
    return pyotp.TOTP(user.test_totp_secret).now()  # type: ignore[attr-defined]


def api_login(
    client: APIClient, user: User, *, password: str = PASSWORD, remember: bool = False
) -> Response:
    response: Response = client.post(
        "/api/v1/auth/login",
        {"login": user.login, "password": password, "remember": remember},
        format="json",
    )
    if response.status_code == 200 and response.data["step"] == "totp":
        # Each login in a test may reuse the current 30-second code.
        User.objects.filter(pk=user.pk).update(totp_last_counter=None)
        response = client.post("/api/v1/auth/totp", {"code": totp_code(user)}, format="json")
    return response


@pytest.fixture
def client_for(make_user: MakeUser) -> Callable[..., APIClient]:
    """client_for(user) → a logged-in APIClient."""

    def factory(user: User, *, remember: bool = False, ip: str = "127.0.0.1") -> APIClient:
        client = APIClient(REMOTE_ADDR=ip)
        response = api_login(client, user, remember=remember)
        assert response.status_code == 200, response.data
        assert response.data == {"step": "done"}
        return client

    return factory


@pytest.fixture
def admin(make_user: MakeUser) -> User:
    return make_user(Role.ADMIN, login="admin", last_name="Каримова", first_name="Дилноза")


@pytest.fixture
def teacher(make_user: MakeUser) -> User:
    return make_user(Role.TEACHER, login="teacher", last_name="Юсупов", first_name="Тимур")


@pytest.fixture
def student(make_user: MakeUser) -> User:
    return make_user(Role.STUDENT, login="student", last_name="Алиев", first_name="Фарход")


@pytest.fixture
def admin_client(admin: User, client_for: Callable[..., APIClient]) -> APIClient:
    return client_for(admin)
