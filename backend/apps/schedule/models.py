"""Week template, concrete lessons and exceptions (SPEC §9).

Dates and times of lessons are civil dates and wall-clock times in the center's time zone,
not instants: a lesson «at 14:00» stays at 14:00 whatever the UTC offset.
"""

import uuid
from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Exists, F, OuterRef, Q

from apps.academics.models import Course, GroupMembership, LessonType, Room


class Weekday(models.IntegerChoices):
    """ISO weekday; the week starts on Monday (SPEC §2)."""

    MONDAY = 1, "понедельник"
    TUESDAY = 2, "вторник"
    WEDNESDAY = 3, "среда"
    THURSDAY = 4, "четверг"
    FRIDAY = 5, "пятница"
    SATURDAY = 6, "суббота"
    SUNDAY = 7, "воскресенье"


class ScheduleSlot(models.Model):
    """A weekly recurring lesson of a course, valid for a period."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="slots")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.ForeignKey(
        Room, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    lesson_type = models.ForeignKey(
        LessonType, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering: ClassVar = ["weekday", "start_time"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="schedule_slot_times"
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=1) & Q(weekday__lte=7), name="schedule_slot_weekday"
            ),
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=F("valid_from")),
                name="schedule_slot_period",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.course} {self.get_weekday_display()} {self.start_time:%H:%M}"


class LessonStatus(models.TextChoices):
    PLANNED = "planned", "запланировано"
    CONDUCTED = "conducted", "проведено"
    CANCELLED = "cancelled", "отменено"


class LessonQuerySet(models.QuerySet["Lesson"]):
    def for_user(self, user: Any, role: str | None) -> "LessonQuerySet":
        """Lessons visible in the given active role. Anything else must look like 404.

        * admin — all;
        * teacher — own courses, courses they assist, lessons where they substitute;
        * student — lessons of groups the student belonged to on the lesson's date.
        """
        if role == "admin":
            return self.all()
        if role == "teacher":
            return self.filter(
                Q(course__teacher=user) | Q(course__assistants=user) | Q(teacher=user)
            ).distinct()
        if role == "student":
            membership = GroupMembership.objects.filter(
                group=OuterRef("course__group"),
                student=user,
                joined_on__lte=OuterRef("date"),
            ).filter(Q(left_on__isnull=True) | Q(left_on__gte=OuterRef("date")))
            return self.filter(Exists(membership))
        return self.none()


class Lesson(models.Model):
    """A concrete lesson. `planned_*` keep what the template said; the actual fields can be
    changed by exceptions (move, room change). A moved lesson is the same row, so anything
    attached to it stays (decision of stage 2)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="lessons")
    slot = models.ForeignKey(
        ScheduleSlot, on_delete=models.PROTECT, null=True, blank=True, related_name="lessons"
    )
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.ForeignKey(
        Room, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Who actually teaches; differs from course.teacher when substituted.
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lessons_taught"
    )
    lesson_type = models.ForeignKey(
        LessonType, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    topic = models.CharField(max_length=300, blank=True)
    homework = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=LessonStatus.choices, default=LessonStatus.PLANNED
    )
    cancel_reason = models.CharField(max_length=300, blank=True)
    # A one-off lesson added by an administrator (consultation, mock test).
    is_extra = models.BooleanField(default=False)
    planned_date = models.DateField()
    planned_start_time = models.TimeField()
    planned_end_time = models.TimeField()
    planned_room = models.ForeignKey(
        Room, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    # Optimistic locking (SPEC §10.12): every change increments it.
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LessonQuerySet.as_manager()

    class Meta:
        ordering: ClassVar = ["date", "start_time"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="schedule_lesson_times"
            ),
            # Idempotent generation: one lesson per slot and template date.
            models.UniqueConstraint(
                fields=["slot", "planned_date"],
                condition=Q(slot__isnull=False),
                name="schedule_lesson_slot_date_unique",
            ),
            models.CheckConstraint(
                condition=~Q(status=LessonStatus.CANCELLED) | ~Q(cancel_reason=""),
                name="schedule_lesson_cancel_reason",
            ),
        ]
        indexes: ClassVar = [
            models.Index(fields=["course", "date"]),
            models.Index(fields=["teacher", "date"]),
            models.Index(fields=["room", "date"]),
        ]

    def __str__(self) -> str:
        return f"{self.course} {self.date} {self.start_time:%H:%M}"

    @property
    def is_moved(self) -> bool:
        return (
            self.date != self.planned_date
            or self.start_time != self.planned_start_time
            or self.end_time != self.planned_end_time
        )

    @property
    def is_room_changed(self) -> bool:
        return self.room_id != self.planned_room_id

    @property
    def is_exception(self) -> bool:
        """Changed by hand: the template must not overwrite it."""
        return (
            self.is_moved
            or self.is_room_changed
            or self.status != LessonStatus.PLANNED
            or self.teacher_id != self.course.teacher_id
            or bool(self.topic or self.homework)
        )


class ScheduleRequest(models.Model):
    """A teacher asks the administrator to cancel or move a lesson (SPEC §9)."""

    class Kind(models.TextChoices):
        CANCEL = "cancel", "отмена"
        MOVE = "move", "перенос"

    class Status(models.TextChoices):
        PENDING = "pending", "ожидает"
        APPROVED = "approved", "одобрен"
        REJECTED = "rejected", "отклонён"
        WITHDRAWN = "withdrawn", "отозван"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="requests")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="schedule_requests"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    proposed_date = models.DateField(null=True, blank=True)
    proposed_start_time = models.TimeField(null=True, blank=True)
    proposed_end_time = models.TimeField(null=True, blank=True)
    proposed_room = models.ForeignKey(
        Room, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_comment = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar = ["-created_at"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=~Q(kind="move")
                | (
                    Q(proposed_date__isnull=False)
                    & Q(proposed_start_time__isnull=False)
                    & Q(proposed_end_time__isnull=False)
                ),
                name="schedule_request_move_has_time",
            ),
            models.UniqueConstraint(
                fields=["lesson"],
                condition=Q(status="pending"),
                name="schedule_request_one_pending_per_lesson",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.lesson_id} ({self.status})"
