"""Mock exams (SPEC §5, §6.4, §7.6, §8.7).

A test has a maximum and optional sections; when it has sections, the total is the sum of
the section scores. Students' goals are per subject, in % of the maximum (decision of
stage 5), so tests with different maxima are comparable on one chart.
"""

import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.academics.models import Course, Subject


class Exam(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="exams")
    courses = models.ManyToManyField(Course, related_name="exams")
    date = models.DateField()
    max_score = models.PositiveSmallIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering: ClassVar = ["-date", "title"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(max_score__gte=1) & Q(max_score__lte=1000), name="exams_exam_max_score"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.date} {self.title}"


class ExamSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=120)
    max_score = models.PositiveSmallIntegerField()
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering: ClassVar = ["position", "name"]
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["exam", "name"], name="exams_section_name_unique"),
            models.CheckConstraint(condition=Q(max_score__gte=1), name="exams_section_max_score"),
        ]

    def __str__(self) -> str:
        return self.name


class ExamResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="results")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="exam_results"
    )
    # NULL only when the student was absent.
    total = models.PositiveSmallIntegerField(null=True, blank=True)
    was_absent = models.BooleanField(default=False)
    comment = models.CharField(max_length=300, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["exam", "student"], name="exams_result_unique"),
            models.CheckConstraint(
                condition=(Q(was_absent=True) & Q(total__isnull=True))
                | (Q(was_absent=False) & Q(total__isnull=False)),
                name="exams_result_total_or_absent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.exam_id} {self.student_id}: {self.total}"


class ExamSectionScore(models.Model):
    result = models.ForeignKey(ExamResult, on_delete=models.CASCADE, related_name="section_scores")
    section = models.ForeignKey(ExamSection, on_delete=models.CASCADE, related_name="+")
    score = models.PositiveSmallIntegerField()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["result", "section"], name="exams_section_score_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.section_id}: {self.score}"


class StudentTarget(models.Model):
    """A student's goal for a subject, in % of the maximum (decision of stage 5)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="targets"
    )
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="+")
    percent = models.PositiveSmallIntegerField()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["student", "subject"], name="exams_target_unique"),
            models.CheckConstraint(
                condition=Q(percent__gte=1) & Q(percent__lte=100), name="exams_target_percent"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} {self.subject_id}: {self.percent}%"
