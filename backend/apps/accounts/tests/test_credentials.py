import pytest

from apps.accounts import credentials
from apps.accounts.models import Role
from conftest import MakeUser


@pytest.mark.parametrize(
    ("last", "first", "expected"),
    [
        ("Алиев", "Фарход", "aliev.f"),
        ("Ёлкина", "Юлия", "yolkina.y"),
        ("Щукин", "Эдуард", "shchukin.e"),
        ("Ўринбоев", "Қодир", "orinboev.q"),
        ("Хасанова", "Ғулом", "khasanova.g"),
        ("Kim", "Sergey", "kim.s"),
        ("О'Брайен", "Анна", "obrayen.a"),
    ],
)
def test_login_base(last: str, first: str, expected: str) -> None:
    assert credentials.login_base(last, first) == expected


@pytest.mark.django_db
def test_generated_login_skips_taken_including_archived(make_user: MakeUser) -> None:
    from django.utils import timezone

    make_user(Role.STUDENT, login="aliev.f", archived_at=timezone.now(), is_active=False)
    make_user(Role.STUDENT, login="aliev.f2")
    assert credentials.generate_login("Алиев", "Фарход") == "aliev.f3"
    # A similar prefix is not a collision.
    make_user(Role.STUDENT, login="aliev.fa")
    assert credentials.generate_login("Алиев", "Фарход") == "aliev.f3"


def test_temporary_password_has_no_look_alikes() -> None:
    for _ in range(200):
        password = credentials.generate_temporary_password()
        assert len(password) == 12
        assert not set(password) & set("0Oo1lI")


@pytest.mark.parametrize(
    ("login", "ok"),
    [("aliev.f", True), ("aliev.f2", True), ("a", False), ("bad login", False), (".x", False)],
)
def test_login_format(login: str, ok: bool) -> None:
    assert credentials.is_valid_login(login) is ok
