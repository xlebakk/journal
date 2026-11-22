"""Monitoring for the administrator (stage 7) and the server-side commands."""

import io
import json
import logging
import time
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import sessions
from apps.accounts.models import LoginEvent, Role, User
from apps.audit.models import DeniedRequest
from apps.core.logging import JsonFormatter
from apps.core.models import CenterSettings
from conftest import MakeUser

ClientFor = Callable[..., APIClient]


@pytest.mark.django_db
class TestDeniedRequests:
    def test_probing_ids_is_recorded(self, student: User, client_for: ClientFor) -> None:
        client = client_for(student)
        assert client.get(f"/api/v1/student/grades/{uuid.uuid4()}").status_code == 404
        assert client.get("/api/v1/admin/users").status_code == 403
        rows = list(DeniedRequest.objects.order_by("at").values_list("status", "role", "path"))
        assert rows[0][:2] == (404, "student")
        assert rows[1] == (403, "student", "/api/v1/admin/users")

    def test_normal_refusals_are_not_counted(
        self, admin: User, make_user: MakeUser, client_for: ClientFor
    ) -> None:
        # Anonymous, «enter the password again» and forced password change are not probing.
        APIClient().get("/api/v1/admin/users")
        client = client_for(admin)
        session = client.session
        session[sessions.REAUTH_AT] = time.time() - 600
        session.save()
        other = make_user(Role.TEACHER, totp_enabled=True)
        response = client.post(f"/api/v1/admin/users/{other.pk}/reset-2fa", {}, format="json")
        assert response.json() == {"detail": "reauth_required"}
        newbie = make_user(Role.STUDENT, must_change_password=True)
        assert client_for(newbie).get("/api/v1/student/home").status_code == 403
        assert not DeniedRequest.objects.exists()

    def test_overview_shows_spikes_first(
        self, student: User, make_user: MakeUser, admin_client: APIClient
    ) -> None:
        calm = make_user(Role.STUDENT)
        DeniedRequest.objects.bulk_create(
            [DeniedRequest(user=student, method="GET", path="/api/v1/x", status=404)] * 12
            + [DeniedRequest(user=calm, method="GET", path="/api/v1/y", status=403)] * 2
        )
        old = DeniedRequest.objects.filter(user=calm).first()
        assert old is not None
        DeniedRequest.objects.filter(pk=old.pk).update(at=timezone.now() - timedelta(hours=3))
        denied = admin_client.get("/api/v1/admin/overview").json()["denied"]
        assert [(d["full_name"], d["count"], d["last_hour"], d["spike"]) for d in denied] == [
            (student.full_name, 12, 12, True),
            (calm.full_name, 2, 1, False),
        ]

    def test_prune_keeps_thirty_days(self, student: User) -> None:
        fresh = DeniedRequest.objects.create(user=student, method="GET", path="/a", status=404)
        stale = DeniedRequest.objects.create(user=student, method="GET", path="/b", status=404)
        DeniedRequest.objects.filter(pk=stale.pk).update(at=timezone.now() - timedelta(days=31))
        call_command("prune_security_log", stdout=io.StringIO())
        assert list(DeniedRequest.objects.values_list("pk", flat=True)) == [fresh.pk]


@pytest.mark.django_db
def test_admin_logins_from_new_devices(admin: User, admin_client: APIClient) -> None:
    LoginEvent.objects.all().delete()
    old_browser = "Mozilla/5.0 (Windows NT 10.0) Firefox/140.0"
    first = LoginEvent.objects.create(
        user=admin, login_attempted=admin.login, success=True, reason="ok", user_agent=old_browser
    )
    LoginEvent.objects.filter(pk=first.pk).update(at=timezone.now() - timedelta(days=30))
    for agent in (old_browser, "Dalvik/2.1.0 (Linux; Android 15)"):
        LoginEvent.objects.create(
            user=admin, login_attempted=admin.login, success=True, reason="ok", user_agent=agent
        )
    devices = admin_client.get("/api/v1/admin/overview").json()["admin_new_devices"]
    assert [d["user_agent"] for d in devices] == ["Dalvik/2.1.0 (Linux; Android 15)"]


@pytest.mark.django_db
def test_backup_status_reaches_the_settings(admin_client: APIClient) -> None:
    call_command("backup_status", "--backup", "ok", stdout=io.StringIO())
    call_command("backup_status", "--restore-check", "failed", stdout=io.StringIO())
    center = CenterSettings.load()
    assert center.last_backup_ok is True
    assert center.last_restore_check_ok is False
    body = admin_client.get("/api/v1/admin/settings").json()
    assert body["last_backup_ok"] is True
    assert body["last_restore_check_ok"] is False
    # Read-only through the API.
    admin_client.patch("/api/v1/admin/settings", {"last_backup_ok": False}, format="json")
    assert CenterSettings.load().last_backup_ok is True


@pytest.mark.django_db
def test_db_grants_refuses_to_run_as_the_app_role(settings: Any) -> None:
    role = settings.DATABASES["default"]["USER"]
    with pytest.raises(CommandError, match="owner"):
        call_command("db_grants", "--app-role", role, stdout=io.StringIO())


def test_json_logs_keep_context_and_drop_the_request() -> None:
    record = logging.makeLogRecord(
        {"name": "apps.x", "levelname": "WARNING", "msg": "denied %s", "args": ("x",)}
    )
    record.request = object()
    record.user_id = "u1"
    line = json.loads(JsonFormatter().format(record))
    assert line["message"] == "denied x"
    assert line["level"] == "WARNING"
    assert line["user_id"] == "u1"
    assert "request" not in line
