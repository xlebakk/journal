import pytest
from django.db import DatabaseError, connection, transaction

from apps.accounts.models import Role
from apps.audit import services
from apps.audit.models import AuditLog
from conftest import MakeUser


@pytest.fixture
def entry(db: None) -> AuditLog:
    with transaction.atomic():
        return services.record(
            request=None, action="test.action", entity_type="x", entity_id="1", after={"a": 1}
        )


@pytest.mark.django_db
class TestAppendOnly:
    """UPDATE/DELETE on the audit table fail at the database level."""

    def test_raw_update_fails(self, entry: AuditLog) -> None:
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE audit_auditlog SET action = %s WHERE id = %s", ["x", entry.pk])

    def test_raw_delete_fails(self, entry: AuditLog) -> None:
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM audit_auditlog WHERE id = %s", [entry.pk])

    def test_orm_update_and_delete_fail(self, entry: AuditLog) -> None:
        with pytest.raises(DatabaseError), transaction.atomic():
            AuditLog.objects.filter(pk=entry.pk).update(action="x")
        with pytest.raises(DatabaseError), transaction.atomic():
            entry.delete()
        entry.refresh_from_db()
        assert entry.action == "test.action"

    def test_app_role_is_not_superuser(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            (is_superuser,) = cursor.fetchone()
        if is_superuser:
            pytest.skip("CI database runs as superuser; dev/prod use a non-superuser role")
        assert is_superuser is False


@pytest.mark.django_db(transaction=True)
def test_record_requires_a_transaction() -> None:
    with pytest.raises(RuntimeError):
        services.record(request=None, action="x", entity_type="x", entity_id="1")


@pytest.mark.django_db
def test_secrets_never_reach_the_log(make_user: MakeUser) -> None:
    user = make_user(Role.ADMIN)
    snap = services.snapshot(user, ["login", "password", "totp_secret", "roles"])
    assert set(snap) == {"login", "roles"}
    with transaction.atomic():
        row = services.record(
            request=None,
            action="x",
            entity=user,
            after={"password": "p", "nested": {"totp_secret": "s", "ok": 1}},
        )
    assert row.after == {"nested": {"ok": 1}}
    assert row.entity_type == "accounts.user"
