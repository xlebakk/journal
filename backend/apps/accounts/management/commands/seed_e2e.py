"""Fresh database for Playwright: wipes the *_e2e database, migrates, adds fixed users.

The audit log cannot be deleted row by row (trigger), so the whole schema is recreated.
"""

from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts import totp
from apps.accounts.models import Role, StudentProfile, TeacherProfile, User

# Throwaway test database only.
E2E_PASSWORD = "e2e-password-2026"
E2E_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


class Command(BaseCommand):
    help = "Recreates the e2e database with fixed users. Refuses to touch any other database."

    def handle(self, *args: Any, **options: Any) -> None:
        name = str(settings.DATABASES["default"]["NAME"])
        if not settings.DEBUG or not name.endswith("_e2e"):
            raise CommandError(f"seed_e2e only runs with DEBUG on a *_e2e database, not {name!r}")
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        call_command("migrate", verbosity=0)

        with transaction.atomic():

            def make(login: str, roles: list[str], last: str, first: str, **extra: Any) -> User:
                return User.objects.create_user(
                    login=login,
                    password=E2E_PASSWORD,
                    last_name=last,
                    first_name=first,
                    roles=roles,
                    must_change_password=extra.pop("must_change_password", False),
                    **extra,
                )

            admin = make(
                "e2e.admin",
                [Role.ADMIN],
                "Каримова",
                "Дилноза",
                totp_enabled=True,
                totp_secret=totp.encrypt_secret(E2E_TOTP_SECRET),
            )
            teacher = make("e2e.teacher", [Role.TEACHER], "Юсупов", "Тимур")
            TeacherProfile.objects.create(user=teacher)
            student = make("e2e.student", [Role.STUDENT], "Алиев", "Фарход")
            StudentProfile.objects.create(user=student)
            newbie = make("e2e.new", [Role.STUDENT], "Новикова", "Анна", must_change_password=True)
            StudentProfile.objects.create(user=newbie)
        logins = ", ".join(u.login for u in (admin, teacher, student, newbie))
        self.stdout.write(f"e2e users ready: {logins}")
