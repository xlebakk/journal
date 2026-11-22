"""Schedule as an iCalendar feed (RFC 5545) for a personal subscription link (SPEC §16.7).

Events are the lessons the owner sees in the feed's role (`Lesson.objects.for_user`), from a
month back to four months ahead. Times are converted from the center's civil time to UTC.
A cancelled lesson stays in the feed with STATUS:CANCELLED so that calendars remove it.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.accounts.models import User

from . import services
from .models import CalendarFeed, Lesson, LessonStatus

SALT = "journal.schedule.calendar-feed"
DAYS_BACK = 31
DAYS_AHEAD = 120


def token_for(feed_id: Any, secret: str | None = None) -> str:
    return salted_hmac(SALT, str(feed_id), secret=secret, algorithm="sha256").hexdigest()


def check_token(feed_id: Any, token: str) -> bool:
    """Links survive a SECRET_KEY rotation while the old key is in SECRET_KEY_FALLBACKS."""
    secrets = [settings.SECRET_KEY, *getattr(settings, "SECRET_KEY_FALLBACKS", [])]
    return any(constant_time_compare(token_for(feed_id, s), token) for s in secrets)


def escape(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\r\n", r"\n")
        .replace("\n", r"\n")
    )


def fold(line: str) -> str:
    """Lines of at most 75 octets; continuation lines start with a space (RFC 5545 §3.1)."""
    parts: list[str] = []
    current, size = "", 0
    for ch in line:
        width = len(ch.encode())
        limit = 75 if not parts else 74
        if size + width > limit:
            parts.append(current)
            current, size = "", 0
        current += ch
        size += width
    parts.append(current)
    return "\r\n ".join(parts)


def _utc(day: date, at: time) -> str:
    local = datetime.combine(day, at, tzinfo=ZoneInfo(settings.TIME_ZONE))
    return local.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _event(lesson: Lesson, feed: CalendarFeed) -> list[str]:
    user = feed.user
    course = lesson.course
    title = course.subject.name
    if lesson.lesson_type:
        title += f" ({lesson.lesson_type.short})"
    replaced = lesson.teacher_id != course.teacher_id
    free = False
    if feed.role == "teacher":
        title = f"{course.group.name} · {title}"
        if replaced and course.teacher_id == user.pk:
            title = f"Замена: {lesson.teacher.short_name} · {title}"
            free = True
        elif replaced and lesson.teacher_id == user.pk:
            title = f"Замена · {title}"
    cancelled = lesson.status == LessonStatus.CANCELLED
    if cancelled:
        title = f"Отменено: {title}"

    notes = []
    if feed.role == "student":
        mark = " (замена)" if replaced else ""
        notes.append(f"Преподаватель: {lesson.teacher.short_name}{mark}")
    if lesson.date != lesson.planned_date or lesson.start_time != lesson.planned_start_time:
        notes.append(f"Перенесено с {lesson.planned_date:%d.%m} {lesson.planned_start_time:%H:%M}")
    if cancelled and lesson.cancel_reason:
        notes.append(f"Причина отмены: {lesson.cancel_reason}")
    if lesson.topic:
        notes.append(f"Тема: {lesson.topic}")
    if lesson.homework:
        notes.append(f"ДЗ: {lesson.homework}")

    lines = [
        "BEGIN:VEVENT",
        f"UID:{lesson.pk}@journal",
        f"DTSTAMP:{_stamp(lesson.updated_at)}",
        f"LAST-MODIFIED:{_stamp(lesson.updated_at)}",
        f"SEQUENCE:{lesson.version}",
        f"DTSTART:{_utc(lesson.date, lesson.start_time)}",
        f"DTEND:{_utc(lesson.date, lesson.end_time)}",
        f"SUMMARY:{escape(title)}",
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
        f"TRANSP:{'TRANSPARENT' if cancelled or free else 'OPAQUE'}",
    ]
    if lesson.room:
        lines.append(f"LOCATION:{escape(lesson.room.name)}")
    if notes:
        lines.append(f"DESCRIPTION:{escape(chr(10).join(notes))}")
    lines.append("END:VEVENT")
    return lines


def lessons(feed: CalendarFeed) -> Iterable[Lesson]:
    day = services.today()
    return (
        Lesson.objects.for_user(feed.user, feed.role)
        .filter(
            date__gte=day - timedelta(days=DAYS_BACK), date__lte=day + timedelta(days=DAYS_AHEAD)
        )
        .select_related("course__subject", "course__group", "room", "teacher", "lesson_type")
        .order_by("date", "start_time")
    )


def render(feed: CalendarFeed, center_name: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//journal//schedule//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(f'{center_name} · расписание')}",
        f"X-WR-TIMEZONE:{settings.TIME_ZONE}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]
    for lesson in lessons(feed):
        lines.extend(_event(lesson, feed))
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + "\r\n" for line in lines)


def is_live(feed: CalendarFeed) -> bool:
    """A link works while its owner can log in and still has the role."""
    owner: User = feed.user
    return owner.can_log_in and feed.role in owner.roles
