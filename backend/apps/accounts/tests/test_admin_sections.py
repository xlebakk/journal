"""A super administrator and administrators with granted sections (stage 16)."""

from collections.abc import Callable

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import OperandHolder
from rest_framework.test import APIClient

from apps.accounts.models import AdminSection, Role, User
from apps.accounts.permissions import ADMIN_PATHS, IsAdmin, admin_section
from conftest import MakeUser

ClientFor = Callable[..., APIClient]
USERS = "/api/v1/admin/users"
PASSWORD = "надёжный пароль администратора"


def limited(make_user: MakeUser, *sections: str) -> User:
    return make_user(Role.ADMIN, is_superadmin=False, admin_sections=list(sections))


@pytest.mark.django_db
class TestSections:
    def test_an_admin_opens_only_the_granted_sections(
        self, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        client = client_for(limited(make_user, AdminSection.PAYMENTS))
        assert client.get("/api/v1/admin/payments/students").status_code == 200
        assert client.get("/api/v1/admin/overview").status_code == 200  # every administrator
        for url in (USERS, "/api/v1/admin/settings", "/api/v1/admin/audit", "/api/v1/admin/groups"):
            assert client.get(url).status_code == 403, url

    def test_the_me_endpoint_tells_the_frontend(
        self, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        me = client_for(limited(make_user, AdminSection.USERS)).get("/api/v1/me").json()
        assert (me["is_superadmin"], me["admin_sections"]) == (False, ["users"])

    def test_unlisted_admin_paths_are_super_admin_only(self) -> None:
        assert admin_section("/api/v1/admin/payments/students") == "payments"
        assert admin_section("/api/v1/admin/overview") == ""
        assert admin_section("/api/v1/admin/something-new") is None
        assert admin_section("/api/v1/admin/usersx") is None  # a prefix is a whole segment


@pytest.mark.django_db
class TestManagingAdministrators:
    def test_only_the_super_admin_creates_and_grants(
        self, make_user: MakeUser, client_for: ClientFor, admin_client: APIClient
    ) -> None:
        people = client_for(limited(make_user, AdminSection.USERS))
        teacher = {"last_name": "Ким", "first_name": "Сергей", "password": PASSWORD}
        assert (
            people.post(USERS, {**teacher, "roles": ["teacher"]}, format="json").status_code == 201
        )
        admin_body = {**teacher, "last_name": "Пак", "roles": ["admin"]}
        refused = people.post(USERS, admin_body, format="json")
        assert refused.json() == {"detail": "superadmin_required"}

        granted = admin_client.post(
            USERS, {**admin_body, "admin_sections": ["payments", "reports"]}, format="json"
        ).json()
        assert (granted["is_superadmin"], granted["admin_sections"]) == (
            False,
            ["payments", "reports"],
        )

    def test_an_ordinary_admin_cannot_touch_another_admin(
        self, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        people = client_for(limited(make_user, AdminSection.USERS))
        other = make_user(Role.ADMIN)
        body = {"password": PASSWORD}
        assert people.post(f"{USERS}/{other.pk}/reset-password", body, format="json").json() == {
            "detail": "superadmin_required"
        }
        assert people.post(f"{USERS}/{other.pk}/block").status_code == 403
        patch = people.patch(f"{USERS}/{other.pk}", {"first_name": "Иван"}, format="json")
        assert patch.status_code == 403
        # Ordinary users are theirs to manage.
        student = make_user(Role.STUDENT)
        ok = people.post(f"{USERS}/{student.pk}/reset-password", body, format="json")
        assert ok.status_code == 200

    def test_the_last_super_admin_stays(
        self, admin: User, make_user: MakeUser, admin_client: APIClient
    ) -> None:
        demoted = admin_client.patch(f"{USERS}/{admin.pk}", {"is_superadmin": False}, format="json")
        assert demoted.json() == {"is_superadmin": ["last_superadmin"]}
        second = make_user(Role.ADMIN)
        assert (
            admin_client.patch(
                f"{USERS}/{second.pk}",
                {"is_superadmin": False, "admin_sections": ["audit"]},
                format="json",
            ).status_code
            == 200
        )
        assert admin_client.post(f"{USERS}/{second.pk}/block").status_code == 200

    def test_sections_are_known_codes(self, admin_client: APIClient, make_user: MakeUser) -> None:
        other = make_user(Role.ADMIN, is_superadmin=False)
        response = admin_client.patch(
            f"{USERS}/{other.pk}", {"admin_sections": ["everything"]}, format="json"
        )
        assert response.status_code == 400


def _admin_routes() -> list[str]:
    """Every API route a non-super administrator could reach through IsAdmin."""

    def has_admin(perms: object) -> bool:
        for c in perms:  # type: ignore[attr-defined]
            if c is IsAdmin:
                return True
            if isinstance(c, OperandHolder) and has_admin([c.op1_class, c.op2_class]):
                return True
        return False

    routes = []

    def walk(patterns: list[URLPattern | URLResolver], prefix: str) -> None:
        for p in patterns:
            route = prefix + str(p.pattern)
            if isinstance(p, URLResolver):
                walk(p.url_patterns, route)
                continue
            view = getattr(p.callback, "cls", None) or getattr(p.callback, "view_class", None)
            if view is not None and has_admin(getattr(view, "permission_classes", ())):
                routes.append("/" + route)

    walk(get_resolver().url_patterns, "")
    return routes


def test_every_admin_route_belongs_to_a_section() -> None:
    """A new admin endpoint must be added to ADMIN_PATHS, or only the super admin gets it."""
    missing = [r for r in _admin_routes() if admin_section(r) is None and "schema" not in r]
    assert missing == [], f"add to ADMIN_PATHS: {missing}"
    assert {s for _, s in ADMIN_PATHS} - {""} == set(AdminSection.values)
