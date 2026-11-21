"""The one place where averages and attendance are computed (SPEC §5, §10.13).

Every screen and report calls `course_stats`, so the numbers match everywhere.

* Weighted average = Σ(grade × weight) / Σ(weight) over non-deleted grades of lessons in
  the period, rounded half-up to 2 decimals.
* Attendance % = (present + late) / (conducted lessons that count attendance, on dates the
  student was in the group, − excused) × 100. Excused absences are reported separately.

A fixed number of queries regardless of the number of students and lessons.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Count, F, Sum

from apps.academics.models import Course, GradeScale, GroupMembership
from apps.schedule.models import Lesson, LessonStatus

from .models import Attendance, AttendanceStatus, Grade

TWO_PLACES = Decimal("0.01")
SCALE_MAX = {GradeScale.HUNDRED: 100, GradeScale.FIVE: 5, GradeScale.TEN: 10}


def rounded(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def low_threshold(scale: str, percent: int) -> Decimal:
    """Grades strictly below this are «low» (SPEC §2: below 50 % of the maximum)."""
    return Decimal(SCALE_MAX[GradeScale(scale)]) * Decimal(percent) / Decimal(100)


@dataclass
class StudentStats:
    average: Decimal | None = None
    grades: int = 0
    present: int = 0
    late: int = 0
    absent: int = 0
    excused: int = 0
    # Conducted lessons that count attendance while the student was in the group.
    eligible: int = 0
    attendance_percent: Decimal | None = None
    _weighted: Decimal = field(default=Decimal(0), repr=False)
    _weights: Decimal = field(default=Decimal(0), repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "average": str(self.average) if self.average is not None else None,
            "grades": self.grades,
            "attendance_percent": (
                str(self.attendance_percent) if self.attendance_percent is not None else None
            ),
            "present": self.present,
            "late": self.late,
            "absent": self.absent,
            "excused": self.excused,
            "eligible": self.eligible,
        }


def _member_on(periods: list[tuple[date, date | None]], day: date) -> bool:
    return any(start <= day and (end is None or day <= end) for start, end in periods)


def course_stats(
    course: Course,
    first: date | None = None,
    last: date | None = None,
    students: Iterable[Any] | None = None,
) -> dict[Any, StudentStats]:
    """Stats per student id for one course and an inclusive date range (None = open)."""
    period: dict[str, Any] = {}
    if first is not None:
        period["date__gte"] = first
    if last is not None:
        period["date__lte"] = last
    student_ids = set(students) if students is not None else None

    memberships: dict[Any, list[tuple[date, date | None]]] = defaultdict(list)
    for m in GroupMembership.objects.filter(group_id=course.group_id).values(
        "student_id", "joined_on", "left_on"
    ):
        if student_ids is None or m["student_id"] in student_ids:
            memberships[m["student_id"]].append((m["joined_on"], m["left_on"]))
    result: dict[Any, StudentStats] = {sid: StudentStats() for sid in memberships}

    # Weighted average.
    grades = (
        Grade.objects.alive()
        .filter(lesson__course=course, **{f"lesson__{k}": v for k, v in period.items()})
        .values("student_id")
        .annotate(weighted=Sum(F("value") * F("weight")), weights=Sum("weight"), n=Count("id"))
    )
    for row in grades:
        sid = row["student_id"]
        if student_ids is not None and sid not in student_ids:
            continue
        stats = result.setdefault(sid, StudentStats())
        stats._weighted = Decimal(row["weighted"])
        stats._weights = Decimal(row["weights"])
        stats.grades = int(row["n"])
        if stats._weights > 0:
            stats.average = rounded(stats._weighted / stats._weights)

    # Attendance over conducted lessons that count it.
    lessons = list(
        Lesson.objects.filter(
            course=course,
            status=LessonStatus.CONDUCTED,
            lesson_type__counts_attendance=True,
            **period,
        ).values_list("pk", "date")
    )
    lesson_dates = dict(lessons)
    for sid, periods in memberships.items():
        result[sid].eligible = sum(1 for d in lesson_dates.values() if _member_on(periods, d))
    marks = Attendance.objects.filter(lesson_id__in=lesson_dates).values_list(
        "student_id", "lesson_id", "status"
    )
    for sid, lesson_id, status in marks:
        if sid not in result or not _member_on(memberships[sid], lesson_dates[lesson_id]):
            continue
        stats = result[sid]
        if status == AttendanceStatus.PRESENT:
            stats.present += 1
        elif status == AttendanceStatus.LATE:
            stats.late += 1
        elif status == AttendanceStatus.ABSENT:
            stats.absent += 1
        elif status == AttendanceStatus.EXCUSED:
            stats.excused += 1
    for stats in result.values():
        denominator = stats.eligible - stats.excused
        if denominator > 0:
            stats.attendance_percent = rounded(
                Decimal(stats.present + stats.late) * 100 / Decimal(denominator)
            )
    return result


@dataclass
class GroupSummary:
    students: int
    average: Decimal | None
    attendance_percent: Decimal | None
    low_attendance: int
    low_average: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "students": self.students,
            "average": self.average,
            "attendance_percent": self.attendance_percent,
            "low_attendance": self.low_attendance,
            "low_average": self.low_average,
        }


def summarise_group(
    stats: Iterable[StudentStats], *, attendance_threshold: int, low_below: Decimal
) -> GroupSummary:
    """Course-level numbers for reports (decision of stage 5).

    * Average = the mean of the students' weighted averages: every student counts once,
      however many grades they have.
    * Attendance % = Σ(present + late) / Σ(eligible − excused): the same formula as for one
      student, over the whole group.
    """
    rows = list(stats)
    averages = [s.average for s in rows if s.average is not None]
    attended = sum(s.present + s.late for s in rows)
    denominator = sum(s.eligible - s.excused for s in rows)
    return GroupSummary(
        students=len(rows),
        average=rounded(sum(averages, Decimal(0)) / len(averages)) if averages else None,
        attendance_percent=(
            rounded(Decimal(attended) * 100 / Decimal(denominator)) if denominator > 0 else None
        ),
        low_attendance=sum(
            1
            for s in rows
            if s.attendance_percent is not None and s.attendance_percent < attendance_threshold
        ),
        low_average=sum(1 for s in rows if s.average is not None and s.average < low_below),
    )
