"""Privileges of the application's database role (stage 7).

Production uses two roles: the owner runs migrations; the app connects as a role that may
only read and write rows. It does not own any table, so it cannot drop or alter them or
disable the audit trigger, and it has no UPDATE, DELETE or TRUNCATE on the audit log.

Run as the owner after every `migrate`:
    manage.py db_grants --app-role journal_app
    manage.py db_grants --app-role journal_app --check   # fails if anything is wider
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from psycopg import sql

AUDIT_TABLE = "audit_auditlog"


def grant_statements(role: str, database: str) -> list[sql.Composed]:
    r = sql.Identifier(role)
    return [
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), r),
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(r),
        sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
            r
        ),
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(r),
        sql.SQL(
            "REVOKE TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM {}"
        ).format(r),
        # Append-only: the trigger refuses UPDATE/DELETE, and the role may not even try.
        sql.SQL("REVOKE UPDATE, DELETE ON {} FROM {}").format(sql.Identifier(AUDIT_TABLE), r),
        sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(r),
    ]


def _yes(query: str, params: list[str]) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()
    return bool(row and row[0])


def problems(role: str) -> list[str]:
    """Everything the app role may do beyond reading and writing rows."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles"
            " WHERE rolname = %s",
            [role],
        )
        flags = cursor.fetchone()
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tableowner = %s",
            [role],
        )
        owned = [name for (name,) in cursor.fetchall()]
    if flags is None:
        return [f"role {role} does not exist"]
    names = ("SUPERUSER", "CREATEROLE", "CREATEDB", "BYPASSRLS")
    found = [f"{role} has {name}" for flag, name in zip(flags, names, strict=True) if flag]
    found += [f"{role} owns table {name}" for name in owned]
    if _yes("SELECT has_schema_privilege(%s, 'public', 'CREATE')", [role]):
        found.append(f"{role} may create objects in schema public")
    table_privilege = "SELECT has_table_privilege(%s, %s, %s)"
    for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
        if _yes(table_privilege, [role, AUDIT_TABLE, privilege]):
            found.append(f"{role} may {privilege} {AUDIT_TABLE}")
    for privilege in ("SELECT", "INSERT"):
        if not _yes(table_privilege, [role, AUDIT_TABLE, privilege]):
            found.append(f"{role} cannot {privilege} {AUDIT_TABLE}")
    return found


class Command(BaseCommand):
    help = "Grants the app role row access only; --check verifies nothing wider is allowed."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--app-role", required=True)
        parser.add_argument("--check", action="store_true")

    def handle(self, *args: Any, app_role: str, check: bool, **options: Any) -> None:
        if connection.vendor != "postgresql":
            raise CommandError("PostgreSQL only")
        if app_role == connection.settings_dict["USER"]:
            raise CommandError("run as the owner role, not as the app role itself")
        if not check:
            database = str(connection.settings_dict["NAME"])
            with connection.cursor() as cursor:
                for statement in grant_statements(app_role, database):
                    cursor.execute(statement)
        found = problems(app_role)
        if found:
            raise CommandError("; ".join(found))
        self.stdout.write(self.style.SUCCESS(f"{app_role}: rows only, audit log append-only"))
