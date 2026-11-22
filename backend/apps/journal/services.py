"""Journal rules (SPEC §10). Every write goes through here, inside one transaction with its
audit entry; the lesson row is locked so concurrent writes to one lesson are serialised.

Decisions of stage 3: a staff member edits and deletes only the grades they gave (the
administrator — any); attendance and topic — anyone of the course team; no grade for
«absent» or «excused»; a conducted lesson stays editable within the window.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Max, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request

from apps.academics.models import GradeScale, GroupMembership, LessonType, WorkType, members_on
from apps.accounts.models import Role, User
from apps.accounts.permissions import active_role, current_user
from apps.audit import services as audit
from apps.core.models import CenterSettings
from apps.schedule import services as schedule
from apps.schedule.models import Lesson, LessonStatus
from apps.schedule.services import VersionConflict

from .models import GRADABLE, Attendance, AttendanceStatus, Grade

SCALE_RANGE = {GradeScale.HUNDRED: (0, 100), GradeScale.FIVE: (2, 5), GradeScale.TEN: (1, 10)}
GRADE_AUDIT = ("value", "work_type_id", "weight", "comment", "deleted_at")
ATTENDANCE_AUDIT = ("status", "late_minutes", "comment")
LESSON_AUDIT = ("topic", "homework", "comment", "lesson_type_id", "status")


class Rule(ValidationError):
    """A business rule refused the change: {"detail": "<code>"} with 400."""

    def __init__(self, code: str) -> None:
        super().__init__({"detail": [code]})


class Forbidden(PermissionDenied):
    def __init__(self, code: str) -> None:
        super().__init__(detail=code, code=code)


@dataclass(frozen=True)
class Actor:
    user: User
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN


def actor(request: Request) -> Actor:
    role = active_role(request)
    if role not in (Role.ADMIN, Role.TEACHER):
        raise PermissionDenied()
    return Actor(current_user(request), role)


def lessons_for(who: Actor) -> QuerySet[Lesson]:
    """Lessons the actor may open; anything else is 404 (SPEC §11)."""
    return Lesson.objects.for_user(who.user, who.role)


def today() -> date:
    return schedule.today()


def window_closes_on(lesson: Lesson) -> date:
    return lesson.date + timedelta(days=CenterSettings.load().edit_window_days)


@dataclass(frozen=True)
class Editability:
    editable: bool
    needs_reason: bool
    locked: str | None  # "future" | "cancelled" | "window" | None


def editability(lesson: Lesson, who: Actor) -> Editability:
    if lesson.status == LessonStatus.CANCELLED:
        return Editability(False, False, "cancelled")
    if lesson.date > today():
        return Editability(False, False, "future")
    closed = today() > window_closes_on(lesson)
    if closed and not who.is_admin:
        return Editability(False, False, "window")
    return Editability(True, closed, None)


def require_writable(lesson: Lesson, who: Actor, reason: str) -> None:
    """SPEC §10.2, §10.4: no future or cancelled lessons; after the window only the
    administrator, and only with a reason (400 without one)."""
    state = editability(lesson, who)
    if state.locked == "cancelled":
        raise Rule("lesson_cancelled")
    if state.locked == "future":
        raise Rule("lesson_in_future")
    if state.locked == "window":
        raise Forbidden("edit_window_closed")
    if state.needs_reason and not reason.strip():
        raise Rule("reason_required")


def lock(who: Actor, lesson_id: Any) -> Lesson:
    """The lesson in the actor's scope, row-locked for the rest of the transaction."""
    get_object_or_404(lessons_for(who), pk=lesson_id)  # 404 outside the scope
    return (
        Lesson.objects.select_for_update(of=("self",))
        .select_related("course__group__academic_year", "lesson_type")
        .get(pk=lesson_id)
    )


def members(lesson: Lesson) -> QuerySet[User]:
    """Students who were in the group on the lesson's date (SPEC §10.3)."""
    ids = GroupMembership.objects.filter(members_on(lesson.date), group_id=lesson.course.group_id)
    return User.objects.filter(pk__in=ids.values("student_id")).order_by("last_name", "first_name")


def require_member(lesson: Lesson, student_id: Any) -> User:
    student = members(lesson).filter(pk=student_id).first()
    if student is None:
        raise Rule("student_not_in_group")
    return student


def _record(
    request: Request, action: str, entity: Any, before: Any, after: Any, reason: str
) -> None:
    audit.record(request=request, action=action, entity=entity, before=before, after=after,
                 reason=reason.strip())  # fmt: skip


# --- Lesson header -------------------------------------------------------------------------


def update_lesson(
    request: Request, lesson_id: Any, version: int, changes: dict[str, Any], reason: str
) -> Lesson:
    who = actor(request)
    with transaction.atomic():
        lesson = lock(who, lesson_id)
        require_writable(lesson, who, reason)
        if lesson.version != version:
            raise VersionConflict()
        before = audit.snapshot(lesson, LESSON_AUDIT)
        for name, value in changes.items():
            setattr(lesson, name, value)
        lesson.version += 1
        lesson.save()
        _record(request, "journal.lesson_update", lesson, before,
                audit.snapshot(lesson, LESSON_AUDIT), reason)  # fmt: skip
    return lesson


def conduct(request: Request, lesson_id: Any, version: int, reason: str) -> Lesson:
    """SPEC §10.5: topic, lesson type and attendance of every student are required."""
    who = actor(request)
    with transaction.atomic():
        lesson = lock(who, lesson_id)
        require_writable(lesson, who, reason)
        if lesson.version != version:
            raise VersionConflict()
        if not lesson.topic.strip():
            raise Rule("topic_required")
        if lesson.lesson_type_id is None:
            raise Rule("lesson_type_required")
        marked = set(Attendance.objects.filter(lesson=lesson).values_list("student_id", flat=True))
        if any(s.pk not in marked for s in members(lesson)):
            raise Rule("attendance_incomplete")
        if lesson.status != LessonStatus.CONDUCTED:
            before = audit.snapshot(lesson, LESSON_AUDIT)
            lesson.status = LessonStatus.CONDUCTED
            lesson.version += 1
            lesson.save()
            _record(request, "journal.lesson_conduct", lesson, before,
                    audit.snapshot(lesson, LESSON_AUDIT), reason)  # fmt: skip
    return lesson


# --- Attendance ----------------------------------------------------------------------------


def set_attendance(
    request: Request,
    lesson_id: Any,
    student_id: Any,
    data: dict[str, Any],
    version: int | None,
    reason: str,
) -> Attendance:
    who = actor(request)
    with transaction.atomic():
        lesson = lock(who, lesson_id)
        require_writable(lesson, who, reason)
        student = require_member(lesson, student_id)
        status = data["status"]
        if (
            status not in GRADABLE
            and Grade.objects.alive().filter(lesson=lesson, student=student).exists()
        ):
            raise Rule("has_grades")
        late = data.get("late_minutes") if status == AttendanceStatus.LATE else None
        record = Attendance.objects.filter(lesson=lesson, student=student).first()
        before = audit.snapshot(record, ATTENDANCE_AUDIT) if record else None
        if record is None:
            record = Attendance(lesson=lesson, student=student)
        elif version is None or record.version != version:
            raise VersionConflict()
        else:
            record.version += 1
        record.status = status
        record.late_minutes = late
        record.comment = data.get("comment", record.comment) or ""
        record.marked_by = who.user
        record.save()
        _record(request, "journal.attendance_set", record, before,
                audit.snapshot(record, ATTENDANCE_AUDIT), reason)  # fmt: skip
    return record


def clear_attendance(
    request: Request, lesson_id: Any, student_id: Any, version: int, reason: str
) -> None:
    """Undo of a first mark. A conducted lesson keeps full attendance (SPEC §10.5)."""
    who = actor(request)
    with transaction.atomic():
        lesson = lock(who, lesson_id)
        require_writable(lesson, who, reason)
        if lesson.status == LessonStatus.CONDUCTED:
            raise Rule("lesson_conducted")
        record = get_object_or_404(Attendance, lesson=lesson, student_id=student_id)
        if record.version != version:
            raise VersionConflict()
        before = audit.snapshot(record, ATTENDANCE_AUDIT)
        record.delete()
        _record(request, "journal.attendance_clear", lesson, before, None, reason)


def mark_all_present(request: Request, lesson_id: Any, reason: str) -> list[Attendance]:
    """«Все присутствуют»: unmarked students become present; existing marks stay."""
    who = actor(request)
    with transaction.atomic():
        lesson = lock(who, lesson_id)
        require_writable(lesson, who, reason)
        marked = set(Attendance.objects.filter(lesson=lesson).values_list("student_id", flat=True))
        created = [
            Attendance(
                lesson=lesson, student=s, status=AttendanceStatus.PRESENT, marked_by=who.user
            )
            for s in members(lesson)
            if s.pk not in marked
        ]
        Attendance.objects.bulk_create(created)
        if created:
            _record(request, "journal.attendance_all_present", lesson, None,
                    {"students": [str(a.student_id) for a in created]}, reason)  # fmt: skip
        return list(Attendance.objects.filter(lesson=lesson))


# --- Grades --------------------------------------------------------------------------------


def _check_value(lesson: Lesson, value: int) -> str:
    scale = GradeScale(lesson.course.group.academic_year.grade_scale)
    low, high = SCALE_RANGE[scale]
    if not low <= value <= high:
        raise ValidationError({"value": ["value_out_of_range"]})
    return scale


def _work_type(work_type_id: Any, lesson: Lesson) -> WorkType:
    if work_type_id is None:
        lesson_type: LessonType | None = lesson.lesson_type
        if lesson_type is not None and lesson_type.default_work_type_id:
            return WorkType.objects.get(pk=lesson_type.default_work_type_id)
        found = WorkType.objects.filter(is_archived=False).order_by("weight", "name").first()
        if found is None:
            raise ValidationError({"work_type": ["required"]})
        return found
    work_type = WorkType.objects.filter(pk=work_type_id, is_archived=False).first()
    if work_type is None:
        raise ValidationError({"work_type": ["invalid_work_type"]})
    return work_type


def add_grade(request: Request, lesson_id: Any, data: dict[str, Any], reason: str) -> Grade:
    """SPEC §10.3, §10.6: a member of the group on that date, not absent, at most N grades."""
    who = actor(request)
    key = data.get("client_key")
    with transaction.atomic():
        lesson = lock(who, lesson_id)
        if key:
            # The same request again (stage 13 offline queue): the grade already exists.
            again = Grade.objects.filter(client_key=key, created_by=who.user, lesson=lesson).first()
            if again is not None:
                return again
        require_writable(lesson, who, reason)
        student = require_member(lesson, data["student"])
        mark = Attendance.objects.filter(lesson=lesson, student=student).first()
        if mark is not None and mark.status not in GRADABLE:
            raise Rule("student_absent")
        scale = _check_value(lesson, data["value"])
        work_type = _work_type(data.get("work_type"), lesson)
        alive = Grade.objects.alive().filter(lesson=lesson, student=student)
        limit = CenterSettings.load().max_grades_per_lesson
        if alive.count() >= limit:
            raise Rule("too_many_grades")
        taken = set(alive.values_list("position", flat=True))
        position = next(p for p in range(1, 10) if p not in taken)
        try:
            with transaction.atomic():
                grade = Grade.objects.create(
                    lesson=lesson, student=student, value=data["value"], scale=scale,
                    work_type=work_type, weight=work_type.weight,
                    comment=data.get("comment", ""), position=position, created_by=who.user,
                    client_key=key,
                )  # fmt: skip
        except IntegrityError as exc:  # pragma: no cover — guarded by the lesson lock
            raise Rule("too_many_grades") from exc
        _record(request, "journal.grade_create", grade, None,
                audit.snapshot(grade, GRADE_AUDIT), reason)  # fmt: skip
    return grade


def _lock_grade(who: Actor, grade_id: Any, version: int, reason: str) -> tuple[Grade, Lesson]:
    grade = get_object_or_404(Grade.objects.filter(lesson__in=lessons_for(who)), pk=grade_id)
    lesson = lock(who, grade.lesson_id)
    grade = Grade.objects.select_for_update().get(pk=grade_id)
    require_writable(lesson, who, reason)
    if not who.is_admin and grade.created_by_id != who.user.pk:
        raise Forbidden("not_your_grade")
    if grade.version != version:
        raise VersionConflict()
    return grade, lesson


def update_grade(
    request: Request, grade_id: Any, version: int, data: dict[str, Any], reason: str
) -> Grade:
    who = actor(request)
    with transaction.atomic():
        grade, lesson = _lock_grade(who, grade_id, version, reason)
        if grade.deleted_at is not None:
            raise Rule("grade_deleted")
        before = audit.snapshot(grade, GRADE_AUDIT)
        if "value" in data:
            grade.value = data["value"]
            _check_value(lesson, grade.value)
        if "work_type" in data:
            work_type = _work_type(data["work_type"], lesson)
            grade.work_type = work_type
            grade.weight = work_type.weight
        if "comment" in data:
            grade.comment = data["comment"]
        grade.version += 1
        grade.save()
        _record(request, "journal.grade_update", grade, before,
                audit.snapshot(grade, GRADE_AUDIT), reason)  # fmt: skip
    return grade


def delete_grade(request: Request, grade_id: Any, version: int, reason: str) -> Grade:
    """Soft delete (SPEC §10.7): gone from the journal and averages, kept in the audit."""
    who = actor(request)
    with transaction.atomic():
        grade, _ = _lock_grade(who, grade_id, version, reason)
        if grade.deleted_at is not None:
            return grade
        before = audit.snapshot(grade, GRADE_AUDIT)
        grade.deleted_at = timezone.now()
        grade.deleted_by = who.user
        grade.version += 1
        grade.save()
        _record(request, "journal.grade_delete", grade, before,
                audit.snapshot(grade, GRADE_AUDIT), reason)  # fmt: skip
    return grade


def restore_grade(request: Request, grade_id: Any, version: int, reason: str) -> Grade:
    """Undo of a deletion (the 10-second «отменить» in the UI)."""
    who = actor(request)
    with transaction.atomic():
        grade, lesson = _lock_grade(who, grade_id, version, reason)
        if grade.deleted_at is None:
            return grade
        alive = Grade.objects.alive().filter(lesson=lesson, student_id=grade.student_id)
        if alive.count() >= CenterSettings.load().max_grades_per_lesson:
            raise Rule("too_many_grades")
        taken = set(alive.values_list("position", flat=True))
        before = audit.snapshot(grade, GRADE_AUDIT)
        if grade.position in taken:
            grade.position = next(p for p in range(1, 10) if p not in taken)
        grade.deleted_at = None
        grade.deleted_by = None
        grade.version += 1
        grade.save()
        _record(request, "journal.grade_restore", grade, before,
                audit.snapshot(grade, GRADE_AUDIT), reason)  # fmt: skip
    return grade


def topic_suggestions(lesson: Lesson, limit: int = 15) -> list[str]:
    """Earlier topics of the course, newest first, for the topic field."""
    rows = (
        Lesson.objects.filter(course_id=lesson.course_id, date__lte=lesson.date)
        .exclude(Q(topic="") | Q(pk=lesson.pk))
        .values("topic")
        .annotate(last=Max("date"))
        .order_by("-last")[:limit]
    )
    return [row["topic"] for row in rows]
