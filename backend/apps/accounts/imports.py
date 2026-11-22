"""Students from a CSV/XLSX: preview with errors per line, then one transaction.

Logins and temporary passwords are generated; the passwords are returned once, for the
access cards, and only their hashes are stored.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from django.db import transaction
from rest_framework.request import Request

from apps.academics.models import AcademicYear, Group, GroupMembership
from apps.audit import services as audit
from apps.journal.services import today

from . import credentials
from .models import Role, StudentProfile, User, normalize_login

# Header (lower-cased, «*» stripped) → field.
COLUMNS = {
    "фамилия": "last_name",
    "имя": "first_name",
    "отчество": "middle_name",
    "логин": "login",
    "группа": "group",
    "дата зачисления": "joined_on",
    "телефон": "phone",
    "школа": "school",
    "класс": "school_grade",
    "цель": "target",
    "родитель": "parent_name",
    "телефон родителя": "parent_phone",
}
TEMPLATE_HEADER = [
    "Фамилия*",
    "Имя*",
    "Отчество",
    "Логин",
    "Группа",
    "Дата зачисления",
    "Телефон",
    "Школа",
    "Класс",
    "Цель",
    "Родитель",
    "Телефон родителя",
]
TEMPLATE_EXAMPLE = [
    "Алиев",
    "Фарход",
    "Рустамович",
    "",
    "11-М вечерняя",
    "01.09.2026",
    "+998 90 123 45 67",
    "Школа № 110",
    "11",
    "ТГУ, мехмат",
    "Алиева Нигора",
    "+998 90 765 43 21",
]
LIMITS = {
    "last_name": 100,
    "first_name": 100,
    "middle_name": 100,
    "phone": 32,
    "school": 200,
    "target": 200,
    "parent_name": 200,
    "parent_phone": 32,
}
PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")


@dataclass
class Row:
    line: int
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    group: Group | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "last_name": self.data.get("last_name", ""),
            "first_name": self.data.get("first_name", ""),
            "middle_name": self.data.get("middle_name", ""),
            "login": self.data.get("login", ""),
            "group_name": self.group.name if self.group else self.data.get("group", ""),
            "issues": self.errors,
            "warnings": self.warnings,
        }


def _date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse(table: list[dict[str, str]]) -> list[Row]:
    year = AcademicYear.objects.filter(is_current=True).first()
    groups = (
        {g.name.lower(): g for g in Group.objects.filter(academic_year=year, is_archived=False)}
        if year
        else {}
    )
    rows = [
        Row(line, {COLUMNS[k]: v for k, v in raw.items() if k in COLUMNS})
        for line, raw in enumerate(table, start=2)
    ]
    logins_in_file: dict[str, int] = {}
    for row in rows:
        login = normalize_login(row.data.get("login", ""))
        if login:
            logins_in_file[login] = logins_in_file.get(login, 0) + 1
    taken = set(User.objects.filter(login__in=list(logins_in_file)).values_list("login", flat=True))
    names = [(r.data.get("last_name", ""), r.data.get("first_name", "")) for r in rows]
    existing = set(
        User.objects.with_role(Role.STUDENT)
        .filter(last_name__in=[n[0] for n in names])
        .values_list("last_name", "first_name", "middle_name")
    )
    for row in rows:
        d = row.data
        for name in ("last_name", "first_name"):
            if not d.get(name):
                row.errors.append(f"{name}:required")
        for name, limit in LIMITS.items():
            if len(d.get(name, "")) > limit:
                row.errors.append(f"{name}:too_long")
        if login := normalize_login(d.get("login", "")):
            d["login"] = login
            if not credentials.is_valid_login(login):
                row.errors.append("login:invalid_login")
            elif login in taken:
                row.errors.append("login:login_taken")
            elif logins_in_file[login] > 1:
                row.errors.append("login:duplicate_in_file")
        if group_name := d.get("group"):
            row.group = groups.get(group_name.lower())
            if row.group is None:
                row.errors.append("group:group_not_found")
        joined = d.get("joined_on")
        if joined:
            parsed = _date(joined)
            if parsed is None:
                row.errors.append("joined_on:invalid_date")
            else:
                d["joined_on"] = parsed
        else:
            d["joined_on"] = today()
        if grade := d.get("school_grade"):
            if grade not in ("9", "10", "11"):
                row.errors.append("school_grade:invalid_choice")
            else:
                d["school_grade"] = int(grade)
        else:
            d["school_grade"] = None
        for name in ("phone", "parent_phone"):
            if d.get(name) and not PHONE_RE.match(d[name]):
                row.errors.append(f"{name}:invalid_phone")
        key = (d.get("last_name", ""), d.get("first_name", ""), d.get("middle_name", ""))
        if key in existing:
            row.warnings.append("possible_duplicate")
    return rows


def apply(request: Request, rows: list[Row]) -> list[dict[str, Any]]:
    """Creates everyone or nobody. Returns the one-time credentials for the cards."""
    created: dict[int, dict[str, Any]] = {}
    # Explicit logins first, so a generated one never takes a login the file asks for.
    ordered = sorted(rows, key=lambda r: not r.data.get("login"))
    with transaction.atomic():
        for row in ordered:
            d = row.data
            login = d.get("login") or credentials.generate_login(d["last_name"], d["first_name"])
            password = credentials.generate_temporary_password()
            user = User.objects.create_user(
                login=login,
                password=password,
                last_name=d["last_name"],
                first_name=d["first_name"],
                middle_name=d.get("middle_name", ""),
                roles=[Role.STUDENT],
                must_change_password=True,
            )
            StudentProfile.objects.create(
                user=user,
                phone=d.get("phone", ""),
                school=d.get("school", ""),
                school_grade=d.get("school_grade"),
                target=d.get("target", ""),
                parent_name=d.get("parent_name", ""),
                parent_phone=d.get("parent_phone", ""),
            )
            after: dict[str, Any] = {"login": login, "roles": [Role.STUDENT], "imported": True}
            if row.group is not None:
                GroupMembership.objects.create(
                    group=row.group, student=user, joined_on=d["joined_on"]
                )
                after["group"] = str(row.group.pk)
                after["joined_on"] = d["joined_on"].isoformat()
            audit.record(request=request, action="user.create", entity=user, after=after)
            created[row.line] = {
                "id": user.pk,
                "full_name": user.full_name,
                "login": login,
                "temporary_password": password,
                "group_name": row.group.name if row.group else "",
            }
    return [created[line] for line in sorted(created)]
