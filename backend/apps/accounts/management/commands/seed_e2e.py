"""Fresh database for Playwright: wipes the *_e2e database, migrates, adds fixed users.

The audit log cannot be deleted row by row (trigger), so the whole schema is recreated.
"""

from datetime import time, timedelta
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.academics.models import (
    AcademicYear,
    Course,
    Group,
    GroupMembership,
    LessonType,
    Room,
    Subject,
)
from apps.accounts import totp
from apps.accounts.models import Role, StudentProfile, TeacherProfile, User
from apps.schedule import services
from apps.schedule.models import ScheduleSlot

# Throwaway test database only.
E2E_PASSWORD = "e2e-password-2026"
E2E_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
# A second administrator: one TOTP code cannot be used twice within 30 seconds.
E2E_TOTP_SECRET_2 = "KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU"


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
            make(
                "e2e.admin2",
                [Role.ADMIN],
                "Рахимов",
                "Азиз",
                totp_enabled=True,
                totp_secret=totp.encrypt_secret(E2E_TOTP_SECRET_2),
            )
            self._schedule(teacher, student)
        logins = ", ".join(u.login for u in (admin, teacher, student, newbie))
        self.stdout.write(f"e2e users ready: {logins}")

    def _schedule(self, teacher: User, student: User) -> None:
        """One group with a maths lesson on today's weekday, so this week has a lesson."""
        today = services.today()
        year = AcademicYear.objects.create(
            name="E2E", starts_on=today - timedelta(days=60), ends_on=today + timedelta(days=200),
            is_current=True,
        )  # fmt: skip
        group = Group.objects.create(name="11-М вечерняя", academic_year=year)
        GroupMembership.objects.create(group=group, student=student, joined_on=year.starts_on)
        course = Course.objects.create(
            group=group, subject=Subject.objects.create(name="Математика", short_name="Мат"),
            teacher=teacher,
        )  # fmt: skip
        slot = ScheduleSlot.objects.create(
            course=course, weekday=today.isoweekday(), start_time=time(10), end_time=time(11, 30),
            room=Room.objects.create(name="101", capacity=16), valid_from=year.starts_on,
        )  # fmt: skip
        # A second course for the journal scenario (independent of the cancellation test).
        physics = Course.objects.create(
            group=group,
            subject=Subject.objects.create(name="Физика", short_name="Физ"),
            teacher=teacher,
        )
        physics_slot = ScheduleSlot.objects.create(
            course=physics,
            weekday=today.isoweekday(),
            start_time=time(8),
            end_time=time(9, 30),
            room=slot.room,
            lesson_type=LessonType.objects.get(short="Пр"),
            valid_from=year.starts_on,
        )
        services.generate_lessons(slots=[slot, physics_slot])
