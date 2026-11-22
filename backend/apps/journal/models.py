"""Attendance and grades (SPEC §5, §10).

Every record carries `version` for optimistic locking (SPEC §10.12). Grades are deleted
softly: they leave the journal and the averages but stay in the database and the audit.
"""

import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.academics.models import Course, GradeScale, Term, WorkType
from apps.schedule.models import Lesson


class AttendanceStatus(models.TextChoices):
    PRESENT = "present", "был"
    LATE = "late", "опоздал"
    ABSENT = "absent", "отсутствовал"
    EXCUSED = "excused", "уважительная причина"


# Grades are allowed only for students who were there (decision of stage 3).
GRADABLE = (AttendanceStatus.PRESENT, AttendanceStatus.LATE)


class Attendance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="attendance")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance"
    )
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices)
    late_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.CharField(max_length=300, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    marked_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["lesson", "student"], name="journal_attendance_unique"),
            models.CheckConstraint(
                condition=Q(late_minutes__isnull=True)
                | (
                    Q(status=AttendanceStatus.LATE)
                    & Q(late_minutes__gte=1)
                    & Q(late_minutes__lte=300)
                ),
                name="journal_attendance_late_minutes",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.lesson_id} {self.student_id} {self.status}"


def _scale_range() -> Q:
    """CHECK on the range of the scale the grade was given in (SPEC §5)."""
    return (
        (Q(scale=GradeScale.HUNDRED) & Q(value__gte=0) & Q(value__lte=100))
        | (Q(scale=GradeScale.FIVE) & Q(value__gte=2) & Q(value__lte=5))
        | (Q(scale=GradeScale.TEN) & Q(value__gte=1) & Q(value__lte=10))
    )


class GradeQuerySet(models.QuerySet["Grade"]):
    def alive(self) -> "GradeQuerySet":
        return self.filter(deleted_at__isnull=True)


class Grade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="grades")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="grades"
    )
    value = models.SmallIntegerField()
    # Copied from the academic year when the grade is given; the year's scale is then frozen.
    scale = models.CharField(max_length=3, choices=GradeScale.choices)
    work_type = models.ForeignKey(WorkType, on_delete=models.PROTECT, related_name="+")
    # Copied from the work type when the grade is given (SPEC §5).
    weight = models.DecimalField(max_digits=4, decimal_places=2)
    comment = models.CharField(max_length=300, blank=True)
    # 1..n: a slot among the student's grades for this lesson; with the partial unique index
    # this enforces «no more than N grades» even under concurrent requests.
    position = models.PositiveSmallIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    version = models.PositiveIntegerField(default=1)
    # Stage 13: a key made by the client, so a grade sent again from the offline queue
    # (the answer was lost, not the request) is not created twice.
    client_key = models.UUIDField(null=True, blank=True, unique=True)

    objects = GradeQuerySet.as_manager()

    class Meta:
        ordering: ClassVar = ["position"]
        constraints: ClassVar = [
            models.CheckConstraint(condition=_scale_range(), name="journal_grade_scale_range"),
            models.CheckConstraint(
                condition=Q(position__gte=1) & Q(position__lte=9), name="journal_grade_position"
            ),
            models.CheckConstraint(condition=Q(weight__gt=0), name="journal_grade_weight"),
            models.UniqueConstraint(
                fields=["lesson", "student", "position"],
                condition=Q(deleted_at__isnull=True),
                name="journal_grade_position_unique",
            ),
        ]
        indexes: ClassVar = [models.Index(fields=["student", "lesson"])]

    def __str__(self) -> str:
        return f"{self.student_id}: {self.value} ({self.lesson_id})"


class TeacherReview(models.Model):
    """«Отзыв преподавателя раз в модуль» (SPEC §16.5): two or three sentences about a student's
    strengths and weaknesses in the course's subject. One per course, student and term; the
    student sees it, and it goes into the summary sheet for parents."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="reviews")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews"
    )
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="reviews")
    text = models.TextField(max_length=600)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["course", "student", "term"], name="journal_review_unique"
            ),
            models.CheckConstraint(condition=~Q(text=""), name="journal_review_not_empty"),
        ]

    def __str__(self) -> str:
        return f"review {self.course_id} {self.student_id} {self.term_id}"
