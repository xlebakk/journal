"""The student's own cabinet (SPEC §6). Everything is scoped to the requesting student:
there are no ids of other people in any parameter, and the one detail endpoint (a grade)
answers 404 for anything that is not theirs."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicYear, Course, GroupMembership, Term
from apps.academics.serializers import current_groups_of
from apps.accounts.models import User
from apps.accounts.permissions import IsStudent, current_user
from apps.core.models import CenterSettings
from apps.core.params import date_param, uuid_param
from apps.schedule.models import Lesson, LessonStatus
from apps.schedule.views import lesson_queryset

from . import student_serializers as s
from .models import Attendance, AttendanceStatus, Grade, TeacherReview
from .services import today
from .stats import course_stats, low_threshold, rounded

NEW_GRADES_DAYS = 7
HOMEWORK_DAYS = 14


def current_year() -> AcademicYear | None:
    day = today()
    return (
        AcademicYear.objects.filter(starts_on__lte=day, ends_on__gte=day).first()
        or AcademicYear.objects.filter(is_current=True).first()
    )


def courses_of(student: User, first: date, last: date) -> list[Course]:
    """Courses of the groups the student belonged to at some point of the period —
    after a transfer the old course stays in the history (SPEC §10.9)."""
    groups = GroupMembership.objects.filter(student=student, joined_on__lte=last).filter(
        Q(left_on__isnull=True) | Q(left_on__gte=first)
    )
    return list(
        Course.objects.filter(group_id__in=groups.values("group_id"))
        .select_related("group__academic_year", "subject", "teacher")
        .order_by("subject__name", "group__name")
    )


def _threshold(course: Course) -> Decimal:
    percent = CenterSettings.load().low_grade_percent
    return low_threshold(course.group.academic_year.grade_scale, percent)


def _my_grades(student: User) -> QuerySet[Grade]:
    lessons = Lesson.objects.for_user(student, "student")
    return (
        Grade.objects.alive()
        .filter(student=student, lesson__in=lessons)
        .select_related(
            "lesson__course__subject",
            "lesson__course__group__academic_year",
            "lesson__lesson_type",
            "work_type",
        )
    )


def _grade_row(grade: Grade) -> dict[str, Any]:
    lesson = grade.lesson
    course = lesson.course
    return {
        "id": grade.pk,
        "date": lesson.date,
        "course": course.pk,
        "subject_name": course.subject.name,
        "subject_short": course.subject.short_name,
        "group_name": course.group.name,
        "topic": lesson.topic,
        "lesson_type_short": lesson.lesson_type.short if lesson.lesson_type else None,
        "value": grade.value,
        "work_type_name": grade.work_type.name,
        "weight": grade.weight,
        "comment": grade.comment,
        "given_at": grade.created_at,
        "low": grade.value < _threshold(course),
    }


def _period(request: Request, year: AcademicYear) -> tuple[date, date, str]:
    """?term=<id> | ?term=year; default — the term containing today, else the whole year."""
    raw = request.query_params.get("term")
    if raw == "year":
        return year.starts_on, year.ends_on, "year"
    if term_id := uuid_param(request, "term"):
        term = get_object_or_404(Term, pk=term_id, year=year)
        return term.starts_on, term.ends_on, str(term.pk)
    day = today()
    current = Term.objects.filter(year=year, starts_on__lte=day, ends_on__gte=day).first()
    if current:
        return current.starts_on, current.ends_on, str(current.pk)
    return year.starts_on, year.ends_on, "year"


def _no_year() -> Response:
    """Before the first academic year exists the cabinet is simply empty."""
    raise ValidationError({"detail": ["no_academic_year"]})


class StudentHomeView(APIView):
    """«Главная» (SPEC §6.1)."""

    permission_classes = (IsStudent,)

    @extend_schema(responses=s.StudentHomeSerializer)
    def get(self, request: Request) -> Response:
        me = current_user(request)
        day = today()
        visible = Lesson.objects.for_user(me, "student")
        lessons_today = lesson_queryset(visible).filter(date=day).order_by("start_time")

        since = timezone.now() - timedelta(days=NEW_GRADES_DAYS)
        new_grades = [
            _grade_row(g)
            for g in _my_grades(me).filter(created_at__gte=since).order_by("-created_at")[:20]
        ]

        year = current_year()
        subjects: list[dict[str, Any]] = []
        homework: list[dict[str, Any]] = []
        period_name = ""
        if year is not None:
            term = Term.objects.filter(year=year, starts_on__lte=day, ends_on__gte=day).first()
            first, last = (term.starts_on, term.ends_on) if term else (year.starts_on, year.ends_on)
            period_name = term.name if term else year.name
            for course in courses_of(me, first, min(last, day)):
                stats = course_stats(course, first, last, students=[me.pk]).get(me.pk)
                average = stats.average if stats else None
                subjects.append(
                    {
                        "course": course.pk,
                        "subject_name": course.subject.name,
                        "group_name": course.group.name,
                        "teacher_name": course.teacher.full_name,
                        "average": average,
                        "attendance_percent": stats.attendance_percent if stats else None,
                        "low": average is not None and average < _threshold(course),
                    }
                )
            homework = self._homework(me, visible, day)
        data = {
            "today": day,
            "period_name": period_name,
            "lessons_today": lessons_today,
            "new_grades": new_grades,
            "homework": homework,
            "subjects": subjects,
        }
        return Response(s.StudentHomeSerializer(data).data)

    def _homework(self, me: User, visible: QuerySet[Lesson], day: date) -> list[dict[str, Any]]:
        """The latest homework of each course (last two weeks) and when it is due: the next
        lesson of that course the student will attend."""
        recent = (
            visible.filter(date__lte=day, date__gte=day - timedelta(days=HOMEWORK_DAYS))
            .exclude(homework="")
            .exclude(status=LessonStatus.CANCELLED)
            .select_related("course__subject")
            .order_by("course_id", "-date", "-start_time")
        )
        latest: dict[Any, Lesson] = {}
        for lesson in recent:
            latest.setdefault(lesson.course_id, lesson)
        upcoming: dict[Any, date] = {}
        for course_id, when in (
            visible.filter(course_id__in=latest, date__gte=day)
            .exclude(status=LessonStatus.CANCELLED)
            .order_by("date", "start_time")
            .values_list("course_id", "date")
        ):
            if when > latest[course_id].date or (when == day and latest[course_id].date < day):
                upcoming.setdefault(course_id, when)
        rows = [
            {
                "lesson": lesson.pk,
                "subject_name": lesson.course.subject.name,
                "assigned_on": lesson.date,
                "topic": lesson.topic,
                "homework": lesson.homework,
                "due_on": upcoming.get(course_id),
            }
            for course_id, lesson in latest.items()
        ]
        return sorted(rows, key=lambda r: (r["due_on"] or date.max, r["subject_name"]))


class StudentDiaryView(APIView):
    """«Дневник»: a week of lessons with topics, homework, own marks and grades (SPEC §6.2)."""

    permission_classes = (IsStudent,)

    @extend_schema(parameters=[OpenApiParameter("week", str)], responses=s.DiarySerializer)
    def get(self, request: Request) -> Response:
        me = current_user(request)
        day = date_param(request, "week") or today()
        monday = day - timedelta(days=day.isoweekday() - 1)
        sunday = monday + timedelta(days=6)
        lessons = list(
            lesson_queryset(Lesson.objects.for_user(me, "student"))
            .filter(date__range=(monday, sunday))
            .order_by("date", "start_time")
        )
        ids = [lesson.pk for lesson in lessons]
        attendance = dict(
            Attendance.objects.filter(student=me, lesson_id__in=ids).values_list(
                "lesson_id", "status"
            )
        )
        grades: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for grade in (
            Grade.objects.alive()
            .filter(student=me, lesson_id__in=ids)
            .select_related("work_type", "lesson__course__group__academic_year")
        ):
            grades[grade.lesson_id].append(
                {
                    "id": grade.pk,
                    "value": grade.value,
                    "work_type_name": grade.work_type.name,
                    "weight": grade.weight,
                    "comment": grade.comment,
                    "low": grade.value < _threshold(grade.lesson.course),
                }
            )
        context = {"attendance": attendance, "grades": grades}
        data = {"week_start": monday, "today": today(), "lessons": lessons}
        return Response(s.DiarySerializer(data, context=context).data)


class StudentGradesView(APIView):
    """«Оценки»: subjects × dates for a term or the year, weighted averages (SPEC §6.3)."""

    permission_classes = (IsStudent,)

    @extend_schema(parameters=[OpenApiParameter("term", str)], responses=s.StudentGradesSerializer)
    def get(self, request: Request) -> Response:
        me = current_user(request)
        year = current_year()
        if year is None:
            return _no_year()
        first, last, period = _period(request, year)
        by_course: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for grade in (
            _my_grades(me)
            .filter(lesson__date__range=(first, last))
            .order_by("lesson__date", "position")
        ):
            by_course[grade.lesson.course_id].append(_grade_row(grade))
        courses = []
        for course in courses_of(me, first, last):
            stats = course_stats(course, first, last, students=[me.pk]).get(me.pk)
            average = stats.average if stats else None
            courses.append(
                {
                    "course": course.pk,
                    "subject_name": course.subject.name,
                    "group_name": course.group.name,
                    "teacher_name": course.teacher.full_name,
                    "average": average,
                    "low": average is not None and average < _threshold(course),
                    "grades": by_course.get(course.pk, []),
                }
            )
        settings = CenterSettings.load()
        my_reviews = (
            TeacherReview.objects.filter(
                student=me, term__starts_on__lte=last, term__ends_on__gte=first
            )
            .select_related("course__subject", "author", "term")
            .order_by("term__starts_on", "course__subject__name")
        )
        data = {
            "period_from": first,
            "period_to": last,
            "period": period,
            "reviews": [
                {
                    "subject_name": r.course.subject.name,
                    "teacher_name": r.author.full_name,
                    "term_name": r.term.name,
                    "text": r.text,
                    "updated_at": r.updated_at,
                }
                for r in my_reviews
            ],
            "terms": Term.objects.filter(year=year).order_by("starts_on"),
            "scale": year.grade_scale,
            "low_below": low_threshold(year.grade_scale, settings.low_grade_percent),
            "courses": courses,
        }
        return Response(s.StudentGradesSerializer(data).data)


class StudentGradeDetailView(APIView):
    """One grade with its lesson — the student's own only; anyone else's id is 404 (SPEC §15)."""

    permission_classes = (IsStudent,)

    @extend_schema(operation_id="student_grade_detail", responses=s.StudentGradeSerializer)
    def get(self, request: Request, pk: str) -> Response:
        grade = get_object_or_404(_my_grades(current_user(request)), pk=pk)
        return Response(s.StudentGradeSerializer(_grade_row(grade)).data)


class StudentAttendanceView(APIView):
    """«Посещаемость»: per subject and overall for the year so far, a month calendar (SPEC §6.5)."""

    permission_classes = (IsStudent,)

    @extend_schema(
        parameters=[OpenApiParameter("month", str)], responses=s.StudentAttendanceSerializer
    )
    def get(self, request: Request) -> Response:
        me = current_user(request)
        year = current_year()
        if year is None:
            return _no_year()
        day = today()
        first, last = year.starts_on, min(year.ends_on, day)
        rows = []
        attended = counted = excused = 0
        for course in courses_of(me, first, last):
            stats = course_stats(course, first, last, students=[me.pk]).get(me.pk)
            if stats is None:
                continue
            attended += stats.present + stats.late
            counted += stats.eligible - stats.excused
            excused += stats.excused
            rows.append(
                {
                    "course": course.pk,
                    "subject_name": course.subject.name,
                    "group_name": course.group.name,
                    "percent": stats.attendance_percent,
                    "present": stats.present,
                    "late": stats.late,
                    "absent": stats.absent,
                    "excused": stats.excused,
                    "eligible": stats.eligible,
                }
            )
        overall = None
        if counted > 0:
            overall = rounded(Decimal(attended) * 100 / Decimal(counted))

        month = self._month(request, day)
        month_end = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        visible = Lesson.objects.for_user(me, "student").filter(date__range=(month, month_end))
        per_day: dict[date, int] = defaultdict(int)
        for when in visible.exclude(status=LessonStatus.CANCELLED).values_list("date", flat=True):
            per_day[when] += 1
        marks: dict[date, list[dict[str, str]]] = defaultdict(list)
        for record in (
            Attendance.objects.filter(student=me, lesson__in=visible)
            .exclude(status=AttendanceStatus.PRESENT)
            .select_related("lesson__course__subject")
            .order_by("lesson__date", "lesson__start_time")
        ):
            subject = record.lesson.course.subject
            marks[record.lesson.date].append(
                {
                    "subject_short": subject.short_name,
                    "subject_name": subject.name,
                    "status": record.status,
                }
            )
        days = []
        cursor = month
        while cursor <= month_end:
            days.append(
                {"date": cursor, "lessons": per_day.get(cursor, 0), "marks": marks.get(cursor, [])}
            )
            cursor += timedelta(days=1)
        data = {
            "period_from": first,
            "period_to": last,
            "threshold": CenterSettings.load().attendance_threshold_percent,
            "overall": overall,
            "excused": excused,
            "courses": rows,
            "month": month.strftime("%Y-%m"),
            "days": days,
        }
        return Response(s.StudentAttendanceSerializer(data).data)

    @staticmethod
    def _month(request: Request, day: date) -> date:
        raw = request.query_params.get("month")
        if not raw:
            return day.replace(day=1)
        try:
            year, month = (int(x) for x in raw.split("-"))
            return date(year, month, 1)
        except ValueError as exc:
            raise ValidationError({"month": ["invalid_date"]}) from exc


class StudentProfileView(APIView):
    """«Профиль»: name, groups, target (filled in by the administrator) (SPEC §6.7)."""

    permission_classes = (IsStudent,)

    @extend_schema(responses=s.StudentProfileViewSerializer)
    def get(self, request: Request) -> Response:
        me = current_user(request)
        profile = getattr(me, "student_profile", None)
        data = {
            "full_name": me.full_name,
            "login": me.login,
            "groups": [g["name"] for g in current_groups_of(me)],
            "school": profile.school if profile else "",
            "school_grade": profile.school_grade if profile else None,
            "target": profile.target if profile else "",
            "target_score": profile.target_score if profile else None,
        }
        return Response(s.StudentProfileViewSerializer(data).data)
