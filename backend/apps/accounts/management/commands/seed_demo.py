"""Demo data (SPEC §14). Stage 1: people only; groups and lessons are added in stages 2–3."""

import os
import random
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts import credentials
from apps.accounts.models import Role, StudentProfile, TeacherProfile, User

LAST_NAMES = [
    ("Алиев", "Алиева"), ("Каримов", "Каримова"), ("Юсупов", "Юсупова"),
    ("Рахимов", "Рахимова"), ("Ахмедов", "Ахмедова"), ("Исмаилов", "Исмаилова"),
    ("Турсунов", "Турсунова"), ("Хасанов", "Хасанова"), ("Назаров", "Назарова"),
    ("Мирзаев", "Мирзаева"), ("Ким", "Ким"), ("Пак", "Пак"), ("Иванов", "Иванова"),
    ("Абдуллаев", "Абдуллаева"), ("Содиков", "Содикова"), ("Шарипов", "Шарипова"),
]  # fmt: skip
MALE = ["Фарход", "Тимур", "Санжар", "Азиз", "Бобур", "Жасур", "Сергей", "Рустам", "Дилшод"]
FEMALE = ["Мадина", "Дилноза", "Нигора", "Малика", "Севара", "Анна", "Камила", "Зарина"]
SCHOOLS = ["Школа № 110", "Лицей при ТГТУ", "Школа № 64", "Президентская школа", "Школа № 21"]
TARGETS = ["ТУИТ, программная инженерия", "НУУз, математика", "ТашГМУ, лечебное дело",
           "Вестминстер, экономика", "Инха, компьютерные науки"]  # fmt: skip


class Command(BaseCommand):
    help = "Creates demo users and prints their logins and passwords. Never in production."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--seed", type=int, default=2026, help="random seed for names")

    def handle(self, *args: Any, seed: int, **options: Any) -> None:
        module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
        if not settings.DEBUG or module.endswith(".prod"):
            raise CommandError("seed_demo refuses to run outside development (DEBUG=False).")
        if User.objects.exists():
            raise CommandError("The database already has users; seed_demo only fills an empty one.")

        # Demo names only, not security.
        rng = random.Random(seed)  # noqa: S311  # nosec B311
        rows: list[tuple[str, str, str, str]] = []

        def person(female: bool) -> tuple[str, str]:
            last = rng.choice(LAST_NAMES)[1 if female else 0]
            return last, rng.choice(FEMALE if female else MALE)

        def make(roles: list[str], last: str, first: str) -> User:
            password = credentials.generate_temporary_password()
            user = User.objects.create_user(
                login=credentials.generate_login(last, first),
                password=password,
                last_name=last,
                first_name=first,
                roles=roles,
                # Demo convenience: skip the forced change; the admin still sets up 2FA.
                must_change_password=False,
            )
            rows.append((", ".join(roles), user.full_name, user.login, password))
            return user

        with transaction.atomic():
            make([Role.ADMIN], "Администратор", "Демо")
            for i in range(6):
                user = make([Role.TEACHER], *person(female=i % 2 == 1))
                TeacherProfile.objects.create(user=user, phone=f"+998 90 100 00 0{i}")
            for i in range(60):
                user = make([Role.STUDENT], *person(female=i % 2 == 1))
                StudentProfile.objects.create(
                    user=user,
                    school=rng.choice(SCHOOLS),
                    school_grade=rng.choice([9, 10, 11]),
                    target=rng.choice(TARGETS),
                    target_score=rng.choice([150, 170, 180, 190]),
                    parent_name=f"{user.last_name} (родитель)",
                    parent_phone=f"+998 91 200 {i:02d} {i:02d}",
                )

        width = max(len(r[1]) for r in rows)
        self.stdout.write(f"{'роль':<8}  {'ФИО':<{width}}  {'логин':<14}  пароль")
        for roles, name, login, password in rows:
            self.stdout.write(f"{roles:<8}  {name:<{width}}  {login:<14}  {password}")
        self.stdout.write(
            self.style.SUCCESS(
                "\nСоздано: 1 администратор, 6 преподавателей, 60 учеников. "
                "Администратор при первом входе настроит 2FA."
            )
        )
