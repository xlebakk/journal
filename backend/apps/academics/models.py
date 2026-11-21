"""Structure of the center: years, terms, subjects, rooms, groups, courses, catalogs (SPEC §5).

Main idea: course = group + subject + teacher. Schedule, lessons, grades and attendance
hang on the course. A student may belong to several groups.
"""

import uuid
from datetime import date
from typing import ClassVar

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q
from django.db.models.functions import Length, Lower


class DateRange(Func):
    """daterange(start, end, '[]') — inclusive on both ends; NULL end = open."""

    function = "DATERANGE"
    output_field = DateRangeField()


models.CharField.register_lookup(Length)


def inclusive(start: str, end: str) -> DateRange:
    return DateRange(start, end, models.Value("[]"))


class GradeScale(models.TextChoices):
    HUNDRED = "100", "100-балльная (0–100)"
    FIVE = "5", "5-балльная (2–5)"
    TEN = "10", "10-балльная (1–10)"


class AcademicYear(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=40, unique=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_current = models.BooleanField(default=False)
    # Fixed for a year once it has grades (SPEC §10.11, enforced in stage 3).
    grade_scale = models.CharField(
        max_length=3, choices=GradeScale.choices, default=GradeScale.HUNDRED
    )

    class Meta:
        ordering: ClassVar = ["-starts_on"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(ends_on__gt=F("starts_on")), name="academics_year_dates"
            ),
            models.UniqueConstraint(
                fields=["is_current"],
                condition=Q(is_current=True),
                name="academics_one_current_year",
            ),
            ExclusionConstraint(
                name="academics_years_do_not_overlap",
                expressions=[(inclusive("starts_on", "ends_on"), RangeOperators.OVERLAPS)],
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def contains(self, day: date) -> bool:
        return self.starts_on <= day <= self.ends_on


class Term(models.Model):
    """Module: a period for average grades. Terms of one year do not overlap."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="terms")
    name = models.CharField(max_length=60)
    starts_on = models.DateField()
    ends_on = models.DateField()

    class Meta:
        ordering: ClassVar = ["starts_on"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(ends_on__gte=F("starts_on")), name="academics_term_dates"
            ),
            models.UniqueConstraint(fields=["year", "name"], name="academics_term_name_unique"),
            ExclusionConstraint(
                name="academics_terms_do_not_overlap",
                expressions=[
                    ("year", RangeOperators.EQUAL),
                    (
                        inclusive("starts_on", "ends_on"),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.year} · {self.name}"


class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=6)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering: ClassVar = ["name"]
        constraints: ClassVar = [
            models.UniqueConstraint(Lower("name"), name="academics_subject_name_unique"),
            models.CheckConstraint(
                condition=Q(short_name__length__gte=2) & Q(short_name__length__lte=6),
                name="academics_subject_short_name_length",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=60)
    capacity = models.PositiveSmallIntegerField()
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering: ClassVar = ["name"]
        constraints: ClassVar = [
            models.UniqueConstraint(Lower("name"), name="academics_room_name_unique"),
            models.CheckConstraint(condition=Q(capacity__gte=1), name="academics_room_capacity"),
        ]

    def __str__(self) -> str:
        return self.name


class GroupQuerySet(models.QuerySet["Group"]):
    def for_teacher(self, user: models.Model) -> "GroupQuerySet":
        """Groups where the user teaches or assists a course."""
        return self.filter(Q(courses__teacher=user) | Q(courses__assistants=user)).distinct()


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="groups")
    level = models.CharField(max_length=60, blank=True)
    is_archived = models.BooleanField(default=False)

    objects = GroupQuerySet.as_manager()

    class Meta:
        ordering: ClassVar = ["name"]
        constraints: ClassVar = [
            models.UniqueConstraint(
                "academic_year", Lower("name"), name="academics_group_name_unique_in_year"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class GroupMembership(models.Model):
    """History of a group's composition. Periods of one student in one group never overlap."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="memberships")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships"
    )
    joined_on = models.DateField()
    # Last day in the group (inclusive); NULL = still a member.
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering: ClassVar = ["joined_on"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(left_on__isnull=True) | Q(left_on__gte=F("joined_on")),
                name="academics_membership_dates",
            ),
            ExclusionConstraint(
                name="academics_membership_periods_do_not_overlap",
                expressions=[
                    ("group", RangeOperators.EQUAL),
                    ("student", RangeOperators.EQUAL),
                    (
                        inclusive("joined_on", "left_on"),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} in {self.group_id} from {self.joined_on}"

    def active_on(self, day: date) -> bool:
        return self.joined_on <= day and (self.left_on is None or day <= self.left_on)


def members_on(day: date) -> Q:
    """Filter for GroupMembership rows active on a date."""
    return Q(joined_on__lte=day) & (Q(left_on__isnull=True) | Q(left_on__gte=day))


class WorkType(models.Model):
    """Kind of graded work and its weight in the weighted average (SPEC §5)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=60)
    weight = models.DecimalField(max_digits=4, decimal_places=2)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering: ClassVar = ["name"]
        constraints: ClassVar = [
            models.UniqueConstraint(Lower("name"), name="academics_work_type_name_unique"),
            models.CheckConstraint(
                condition=Q(weight__gt=0) & Q(weight__lte=10), name="academics_work_type_weight"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class LessonType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=60)
    short = models.CharField(max_length=5)
    default_work_type = models.ForeignKey(
        WorkType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    counts_attendance = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering: ClassVar = ["sort_order", "name"]
        constraints: ClassVar = [
            models.UniqueConstraint(Lower("name"), name="academics_lesson_type_name_unique"),
        ]

    def __str__(self) -> str:
        return self.name


class CourseQuerySet(models.QuerySet["Course"]):
    def for_staff(self, user: models.Model) -> "CourseQuerySet":
        """Courses the user teaches or assists."""
        return self.filter(Q(teacher=user) | Q(assistants=user)).distinct()


class Course(models.Model):
    """Group + subject + teacher. Assistants have the teacher's rights on the course."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="courses")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="courses")
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="courses_taught"
    )
    assistants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="courses_assisted"
    )

    objects = CourseQuerySet.as_manager()

    class Meta:
        ordering: ClassVar = ["group__name", "subject__name"]
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["group", "subject"], name="academics_course_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.group} · {self.subject}"


class Holiday(models.Model):
    """Non-working day: no lessons are generated (SPEC §5)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering: ClassVar = ["date"]

    def __str__(self) -> str:
        return f"{self.date} {self.name}"
