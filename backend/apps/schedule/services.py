"""Schedule logic: generation from the week template, conflicts, template changes, exceptions.

All checks live here so that every endpoint (and the nightly cron) uses the same rules.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from apps.academics.models import Course, GroupMembership, Holiday, LessonType, Room, members_on
from apps.accounts.models import Role, User
from apps.core.exceptions import Conflict

from .models import Lesson, LessonStatus, ScheduleSlot

HORIZON_DAYS = 28  # lessons are generated four weeks ahead


def today() -> date:
    """«Today» in the center's time zone."""
    return timezone.localdate()


def horizon(start: date | None = None) -> tuple[date, date]:
    first = start or today()
    return first, first + timedelta(days=HORIZON_DAYS - 1)


def daterange(first: date, last: date) -> Iterable[date]:
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


# --- Errors --------------------------------------------------------------------------------


class ScheduleConflict(Conflict):
    default_detail = "schedule_conflict"
    default_code = "schedule_conflict"

    def __init__(self, conflicts: list[dict[str, Any]]) -> None:
        super().__init__()
        self.extra = {"conflicts": conflicts}


class VersionConflict(Conflict):
    """«Запись изменена другим пользователем, обновите страницу»."""

    default_detail = "version_conflict"
    default_code = "version_conflict"


class ConfirmationRequired(Conflict):
    default_detail = "confirmation_required"
    default_code = "confirmation_required"

    def __init__(self, plan: dict[str, Any]) -> None:
        super().__init__()
        self.extra = {"plan": plan}


# --- Template → dates ----------------------------------------------------------------------


@dataclass(frozen=True)
class SlotSpec:
    """The fields of a slot that decide where and when its lessons happen."""

    course: Course
    weekday: int
    start_time: time
    end_time: time
    room: Room | None
    lesson_type: LessonType | None
    valid_from: date
    valid_to: date | None

    @classmethod
    def of(cls, slot: ScheduleSlot) -> SlotSpec:
        return cls(
            slot.course,
            slot.weekday,
            slot.start_time,
            slot.end_time,
            slot.room,
            slot.lesson_type,
            slot.valid_from,
            slot.valid_to,
        )


def holidays_between(first: date, last: date) -> set[date]:
    return set(Holiday.objects.filter(date__range=(first, last)).values_list("date", flat=True))


def spec_dates(spec: SlotSpec, first: date, last: date, holidays: set[date]) -> list[date]:
    """Dates in [first, last] where the template puts a lesson."""
    year = spec.course.group.academic_year
    if spec.course.group.is_archived:
        return []
    lo = max(first, spec.valid_from, year.starts_on)
    hi = min(last, spec.valid_to or last, year.ends_on)
    return [d for d in daterange(lo, hi) if d.isoweekday() == spec.weekday and d not in holidays]


def _lesson_from(spec: SlotSpec, slot: ScheduleSlot, day: date) -> Lesson:
    return Lesson(
        course=spec.course,
        slot=slot,
        date=day,
        start_time=spec.start_time,
        end_time=spec.end_time,
        room=spec.room,
        teacher=spec.course.teacher,
        lesson_type=spec.lesson_type,
        planned_date=day,
        planned_start_time=spec.start_time,
        planned_end_time=spec.end_time,
        planned_room=spec.room,
    )


def generate_lessons(
    first: date | None = None, last: date | None = None, slots: Iterable[ScheduleSlot] | None = None
) -> int:
    """Creates missing lessons from the template. Idempotent: a slot never gets two lessons
    for the same template date, even if one was moved, cancelled or the job runs twice."""
    lo, hi = horizon(first)
    hi = last or hi
    holidays = holidays_between(lo, hi)
    if slots is None:
        slots = ScheduleSlot.objects.filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=lo), valid_from__lte=hi
        ).select_related("course__group__academic_year", "course__teacher", "room", "lesson_type")
    created = 0
    for slot in slots:
        spec = SlotSpec.of(slot)
        wanted = spec_dates(spec, lo, hi, holidays)
        if not wanted:
            continue
        existing = set(
            Lesson.objects.filter(slot=slot, planned_date__in=wanted).values_list(
                "planned_date", flat=True
            )
        )
        new = [_lesson_from(spec, slot, d) for d in wanted if d not in existing]
        Lesson.objects.bulk_create(new, ignore_conflicts=True)
        created += len(new)
    return created


# --- Conflicts -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """A lesson as it would be after the change being checked."""

    day: date
    start: time
    end: time
    course: Course
    teacher_id: Any
    room: Room | None
    exclude_ids: frozenset[Any] = frozenset()


def _describe(lesson: Lesson, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "lesson_id": str(lesson.pk),
        "date": lesson.date.isoformat(),
        "start_time": lesson.start_time.strftime("%H:%M"),
        "end_time": lesson.end_time.strftime("%H:%M"),
        "group": lesson.course.group.name,
        "subject": lesson.course.subject.name,
        "teacher": lesson.teacher.short_name,
        "room": lesson.room.name if lesson.room else None,
    }


def _active_lessons_on(days: set[date]) -> QuerySet[Lesson]:
    return (
        Lesson.objects.filter(date__in=days)
        .exclude(status=LessonStatus.CANCELLED)
        .select_related("course__group", "course__subject", "teacher", "room")
    )


def check_lessons(
    candidates: Sequence[Candidate],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(blocking conflicts, warnings) for the candidate lessons against existing ones.

    Blocking: the same teacher, room or group at an overlapping time.
    Warnings: a student of this group is in another group's lesson at that time;
    the room is smaller than the group.
    """
    if not candidates:
        return [], []
    by_day: dict[date, list[Lesson]] = defaultdict(list)
    for lesson in _active_lessons_on({c.day for c in candidates}):
        by_day[lesson.date].append(lesson)

    conflicts: list[dict[str, Any]] = []
    overlapping_groups: dict[tuple[Any, date], set[Any]] = defaultdict(set)
    for c in candidates:
        for other in by_day[c.day]:
            if other.pk in c.exclude_ids or not (
                other.start_time < c.end and c.start < other.end_time
            ):
                continue
            if other.teacher_id == c.teacher_id:
                conflicts.append({**_describe(other, "teacher"), "at": c.day.isoformat()})
            elif c.room is not None and other.room_id == c.room.pk:
                conflicts.append({**_describe(other, "room"), "at": c.day.isoformat()})
            elif other.course.group_id == c.course.group_id:
                conflicts.append({**_describe(other, "group"), "at": c.day.isoformat()})
            else:
                overlapping_groups[(c.course.group_id, c.day)].add(other.course.group_id)

    warnings: list[dict[str, Any]] = []
    for (group_id, day), others in overlapping_groups.items():
        mine = GroupMembership.objects.filter(members_on(day), group_id=group_id)
        shared = User.objects.filter(
            Exists(mine.filter(student=OuterRef("pk"))),
            Exists(
                GroupMembership.objects.filter(
                    members_on(day), group_id__in=others, student=OuterRef("pk")
                )
            ),
        ).order_by("last_name", "first_name")
        names = [u.short_name for u in shared]
        if names:
            warnings.append({"kind": "students", "date": day.isoformat(), "students": names})
    for c in candidates:
        if c.room is None:
            continue
        size = GroupMembership.objects.filter(members_on(c.day), group_id=c.course.group_id).count()
        if size > c.room.capacity:
            warnings.append(
                {
                    "kind": "capacity",
                    "date": c.day.isoformat(),
                    "room": c.room.name,
                    "capacity": c.room.capacity,
                    "students": size,
                }
            )
            break  # one capacity warning is enough
    return conflicts, warnings


def _periods_overlap(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    return (a_to is None or b_from <= a_to) and (b_to is None or a_from <= b_to)


def check_slot_template(spec: SlotSpec, exclude_slot_id: Any = None) -> list[dict[str, Any]]:
    """Recurring conflicts with other slots: same weekday, overlapping time and period,
    and the same teacher, room or group."""
    others = (
        ScheduleSlot.objects.filter(
            weekday=spec.weekday, start_time__lt=spec.end_time, end_time__gt=spec.start_time
        )
        .exclude(pk=exclude_slot_id)
        .filter(
            Q(course__teacher=spec.course.teacher)
            | Q(course__group=spec.course.group)
            | (Q(room=spec.room) if spec.room is not None else Q(pk__in=[]))
        )
        .select_related("course__group", "course__subject", "course__teacher", "room")
    )
    result = []
    for other in others:
        if not _periods_overlap(spec.valid_from, spec.valid_to, other.valid_from, other.valid_to):
            continue
        if other.course.teacher_id == spec.course.teacher_id:
            kind = "teacher"
        elif spec.room is not None and other.room_id == spec.room.pk:
            kind = "room"
        else:
            kind = "group"
        result.append(
            {
                "kind": kind,
                "slot_id": str(other.pk),
                "weekday": other.weekday,
                "start_time": other.start_time.strftime("%H:%M"),
                "end_time": other.end_time.strftime("%H:%M"),
                "group": other.course.group.name,
                "subject": other.course.subject.name,
                "teacher": other.course.teacher.short_name,
                "room": other.room.name if other.room else None,
            }
        )
    return result


# --- Template changes ----------------------------------------------------------------------


@dataclass
class SlotPlan:
    """What a template change does to existing lessons (confirm with dates)."""

    update: list[Lesson] = field(default_factory=list)
    remove: list[Lesson] = field(default_factory=list)
    add: list[date] = field(default_factory=list)
    kept: list[Lesson] = field(default_factory=list)

    @property
    def touches_existing(self) -> bool:
        return bool(self.update or self.remove)

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "updated": [lesson.date.isoformat() for lesson in self.update],
            "removed": [lesson.date.isoformat() for lesson in self.remove],
            "added": [d.isoformat() for d in self.add],
            "kept_exceptions": [lesson.date.isoformat() for lesson in self.kept],
        }


def plan_slot_change(slot: ScheduleSlot | None, new: SlotSpec | None) -> SlotPlan:
    """Only future, not conducted, untouched lessons follow the template; exceptions stay."""
    lo, hi = horizon()
    holidays = holidays_between(lo, hi)
    plan = SlotPlan()
    wanted = set(spec_dates(new, lo, hi, holidays)) if new else set()
    existing: dict[date, Lesson] = {}
    if slot is not None:
        future = (
            Lesson.objects.filter(slot=slot, planned_date__gte=lo)
            .select_related("course")
            .order_by("planned_date")
        )
        for lesson in future:
            existing[lesson.planned_date] = lesson
            if lesson.is_exception or lesson.date < lo:
                plan.kept.append(lesson)
            elif lesson.planned_date in wanted:
                plan.update.append(lesson)
            else:
                plan.remove.append(lesson)
    plan.add = sorted(d for d in wanted if d not in existing)
    return plan


def template_candidates(spec: SlotSpec, plan: SlotPlan) -> list[Candidate]:
    own = frozenset(lesson.pk for lesson in plan.update + plan.remove)
    days = [lesson.planned_date for lesson in plan.update] + plan.add
    return [
        Candidate(
            d, spec.start_time, spec.end_time, spec.course, spec.course.teacher_id, spec.room, own
        )
        for d in days
    ]


@transaction.atomic
def apply_slot_change(slot: ScheduleSlot, spec: SlotSpec, plan: SlotPlan) -> None:
    for lesson in plan.update:
        lesson.date = lesson.planned_date
        lesson.start_time = lesson.planned_start_time = spec.start_time
        lesson.end_time = lesson.planned_end_time = spec.end_time
        lesson.room = lesson.planned_room = spec.room
        lesson.lesson_type = spec.lesson_type
        lesson.version += 1
        lesson.save()
    Lesson.objects.filter(pk__in=[lesson.pk for lesson in plan.remove]).delete()
    generate_lessons(slots=[slot])


def remove_generated_on(day: date) -> int:
    """A new holiday: untouched planned lessons of that day disappear."""
    if day < today():
        return 0
    lessons = Lesson.objects.filter(date=day, slot__isnull=False).select_related("course")
    doomed = [lesson.pk for lesson in lessons if not lesson.is_exception]
    Lesson.objects.filter(pk__in=doomed).delete()
    return len(doomed)


def remove_future_generated(course_ids: Iterable[Any]) -> int:
    """An archived group: its untouched future lessons disappear."""
    lessons = Lesson.objects.filter(
        course_id__in=list(course_ids), date__gte=today(), slot__isnull=False
    ).select_related("course")
    doomed = [lesson.pk for lesson in lessons if not lesson.is_exception]
    Lesson.objects.filter(pk__in=doomed).delete()
    return len(doomed)


def reassign_future_lessons(course: Course, old_teacher_id: Any) -> int:
    """New course teacher: future planned lessons follow, substitutions stay."""
    return Lesson.objects.filter(
        course=course,
        date__gte=today(),
        status=LessonStatus.PLANNED,
        teacher_id=old_teacher_id,
    ).update(teacher=course.teacher)


# --- Exceptions on one lesson --------------------------------------------------------------


def lock_lesson(lesson_id: Any, version: int) -> Lesson:
    """Row lock + optimistic version check. Must run inside a transaction."""
    lesson = (
        Lesson.objects.select_for_update(of=("self",))
        .select_related("course__group", "course__subject", "course__teacher", "room", "teacher")
        .get(pk=lesson_id)
    )
    if lesson.version != version:
        raise VersionConflict()
    return lesson


def ensure_teacher(user: User) -> None:
    if not (user.has_role(Role.TEACHER) and user.can_log_in):
        raise ValueError("not_a_teacher")


def check_or_raise(candidates: Sequence[Candidate]) -> list[dict[str, Any]]:
    conflicts, warnings = check_lessons(candidates)
    if conflicts:
        raise ScheduleConflict(conflicts)
    return warnings


# --- Availability (stage 19): what the forms may offer --------------------------------------


@dataclass(frozen=True)
class Busy:
    start: time
    end: time
    subject: str
    group: str
    teacher_id: Any
    room_id: Any
    group_id: Any


def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and b_start < a_end


def busy_on_date(day: date, exclude_lesson: Any = None) -> list[Busy]:
    """Every active lesson of the day: the same facts the conflict check uses."""
    lessons = _active_lessons_on({day}).exclude(pk=exclude_lesson)
    return [
        Busy(
            lesson.start_time,
            lesson.end_time,
            lesson.course.subject.name,
            lesson.course.group.name,
            lesson.teacher_id,
            lesson.room_id,
            lesson.course.group_id,
        )
        for lesson in lessons
    ]


def busy_on_weekday(
    weekday: int, valid_from: date, valid_to: date | None, exclude_slot: Any = None
) -> list[Busy]:
    """Every template slot of that weekday whose period meets the given one."""
    slots = (
        ScheduleSlot.objects.filter(weekday=weekday, course__group__is_archived=False)
        .exclude(pk=exclude_slot)
        .select_related("course__group", "course__subject")
    )
    return [
        Busy(
            slot.start_time,
            slot.end_time,
            slot.course.subject.name,
            slot.course.group.name,
            slot.course.teacher_id,
            slot.room_id,
            slot.course.group_id,
        )
        for slot in slots
        if _periods_overlap(valid_from, valid_to, slot.valid_from, slot.valid_to)
    ]


def usual_pairs() -> list[tuple[time, time]]:
    """The pair times the center already uses (from the week template), earliest first."""
    pairs = set(ScheduleSlot.objects.values_list("start_time", "end_time").distinct())
    return sorted(pairs)


def availability(
    course: Course,
    busy: list[Busy],
    start: time | None,
    end: time | None,
) -> dict[str, Any]:
    """Free pairs for the group and its teacher; with a time — free rooms and free teachers of
    the subject. The save still runs the full conflict check; this only shapes the choices."""
    group_busy = [b for b in busy if b.group_id == course.group_id]
    teacher_busy = [b for b in busy if b.teacher_id == course.teacher_id]
    blocked = group_busy + teacher_busy
    free_pairs = [
        {"start": s.strftime("%H:%M"), "end": e.strftime("%H:%M")}
        for s, e in usual_pairs()
        if not any(_overlaps(s, e, b.start, b.end) for b in blocked)
    ]
    result: dict[str, Any] = {
        "group_busy": [
            {
                "start": b.start.strftime("%H:%M"),
                "end": b.end.strftime("%H:%M"),
                "subject": b.subject,
            }
            for b in sorted(group_busy, key=lambda b: b.start)
        ],
        "free_pairs": free_pairs,
        "rooms": [],
        "teachers": [],
    }
    if start is None or end is None:
        return result
    at_time = [b for b in busy if _overlaps(start, end, b.start, b.end)]
    taken_rooms = {b.room_id for b in at_time if b.room_id}
    busy_teachers = {b.teacher_id for b in at_time}
    size = GroupMembership.objects.filter(group=course.group, left_on__isnull=True).count()
    result["rooms"] = [
        {"id": str(room.pk), "name": room.name, "capacity": room.capacity,
         "fits": room.capacity >= size}
        for room in Room.objects.filter(is_archived=False).order_by("name")
        if room.pk not in taken_rooms
    ]  # fmt: skip
    teachers = (
        User.objects.with_role(Role.TEACHER)
        .active()
        .filter(teacher_profile__subjects=course.subject)
        .order_by("last_name", "first_name")
    )
    result["teachers"] = [
        {"id": str(u.pk), "full_name": u.full_name} for u in teachers if u.pk not in busy_teachers
    ]
    return result
