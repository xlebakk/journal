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
        # Administrators in tests are super administrators unless a test says otherwise.
        fields.setdefault("is_superadmin", Role.ADMIN in roles)
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


# --- Center structure (stage 2) -----------------------------------------------------------

from datetime import date, time  # noqa: E402

TODAY = date(2026, 11, 16)  # a Monday inside the 2026/2027 year


@pytest.fixture
def frozen_today(monkeypatch: pytest.MonkeyPatch) -> date:
    """«Today» for the schedule logic (generation horizon, editable lessons)."""
    from apps.schedule import services

    monkeypatch.setattr(services, "today", lambda: TODAY)
    return TODAY


@pytest.fixture
def year(db: None) -> Any:
    from apps.academics.models import AcademicYear

    return AcademicYear.objects.create(
        name="2026/2027", starts_on=date(2026, 9, 1), ends_on=date(2027, 6, 30), is_current=True
    )


@pytest.fixture
def room(db: None) -> Any:
    from apps.academics.models import Room

    return Room.objects.create(name="101", capacity=12)


@pytest.fixture
def big_room(db: None) -> Any:
    from apps.academics.models import Room

    return Room.objects.create(name="Актовый зал", capacity=60)


@pytest.fixture
def math(db: None) -> Any:
    from apps.academics.models import Subject

    return Subject.objects.create(name="Математика", short_name="Мат")


@pytest.fixture
def physics(db: None) -> Any:
    from apps.academics.models import Subject

    return Subject.objects.create(name="Физика", short_name="Физ")


@pytest.fixture
def group(year: Any) -> Any:
    from apps.academics.models import Group

    return Group.objects.create(name="11-М вечерняя", academic_year=year, level="11 класс")


@pytest.fixture
def other_group(year: Any) -> Any:
    from apps.academics.models import Group

    return Group.objects.create(name="11-Ф утренняя", academic_year=year, level="11 класс")


def enroll(
    group: Any, student: User, joined: date = date(2026, 9, 1), left: date | None = None
) -> Any:
    from apps.academics.models import GroupMembership

    return GroupMembership.objects.create(
        group=group, student=student, joined_on=joined, left_on=left
    )


@pytest.fixture
def course(group: Any, math: Any, teacher: User, student: User) -> Any:
    from apps.academics.models import Course

    enroll(group, student)
    return Course.objects.create(group=group, subject=math, teacher=teacher)


@pytest.fixture
def slot(course: Any, room: Any, frozen_today: date) -> Any:
    """Mondays 14:00–15:30 in room 101, from the start of the year; lessons generated."""
    from apps.schedule import services
    from apps.schedule.models import ScheduleSlot

    s = ScheduleSlot.objects.create(
        course=course,
        weekday=1,
        start_time=time(14, 0),
        end_time=time(15, 30),
        room=room,
        valid_from=date(2026, 9, 1),
    )
    services.generate_lessons(slots=[s])
    return s
