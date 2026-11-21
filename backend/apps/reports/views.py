"""Reports (SPEC §7.7, §8.8). Every number comes from `apps.journal.stats`.

JSON is for the screen and the print view; `?export=xlsx|csv` returns a file and, being
an export of personal data, needs the password entered within the last 5 minutes.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicYear, Course, GroupMembership, Term
from apps.accounts.models import Role, User
from apps.accounts.permissions import IsAdmin, IsTeacher, require_recent_password
from apps.core.files import export, export_kind
from apps.core.models import CenterSettings
from apps.core.params import date_param, uuid_param
from apps.exams.models import ExamResult, StudentTarget
from apps.exams.services import percent
from apps.journal import services as journal
from apps.journal.stats import StudentStats, course_stats, low_threshold, summarise_group
from apps.journal.views import course_period, course_roster, courses_for
from apps.schedule.models import Lesson, LessonStatus

from . import serializers as s

PERIOD_PARAMS = [
    OpenApiParameter("term", str),
    OpenApiParameter("from", str),
    OpenApiParameter("to", str),
    OpenApiParameter("export", str, enum=["xlsx", "csv"]),
]


Sheets = list[tuple[str, list[list[Any]]]]


def _file(request: Request, kind: str, name: str, sheets: Sheets) -> HttpResponse:
    require_recent_password(request)
    return export(kind, name, sheets)


def current_year() -> AcademicYear:
    year = AcademicYear.objects.filter(is_current=True).first()
    if year is None:
        raise ValidationError({"detail": ["no_academic_year"]})
    return year


def report_period(request: Request, year: AcademicYear) -> tuple[date, date]:
    """?term= or ?from=&to=; default — the whole current year."""
    if term_id := uuid_param(request, "term"):
        term = get_object_or_404(Term, pk=term_id, year=year)
        return term.starts_on, term.ends_on
    first = date_param(request, "from") or year.starts_on
    last = date_param(request, "to") or year.ends_on
    if first > last:
        raise ValidationError({"to": ["period_reversed"]})
    return first, last


def members_in(course: Course, first: date, last: date) -> list[Any]:
    """Students who were in the group on at least one day of the period."""
    return list(
        GroupMembership.objects.filter(group_id=course.group_id, joined_on__lte=last)
        .filter(Q(left_on__isnull=True) | Q(left_on__gte=first))
        .values_list("student_id", flat=True)
        .distinct()
    )


# --- Teacher: course statement ------------------------------------------------------------


class CourseStatementView(APIView):
    """«Ведомость» of one course for a period: average, attendance, absences per student."""

    permission_classes = (IsAdmin | IsTeacher,)
    throttle_scope = "export"

    @extend_schema(parameters=PERIOD_PARAMS, responses=s.CourseStatementSerializer)
    def get(self, request: Request, pk: str) -> Response | HttpResponse:
        who = journal.actor(request)
        course = get_object_or_404(courses_for(who), pk=pk)
        first, last = course_period(request, course)
        stats = course_stats(course, first, last)
        roster = course_roster(course, first, last, stats)
        settings = CenterSettings.load()
        scale = course.group.academic_year.grade_scale
        summary = summarise_group(
            [stats.get(r["id"]) or StudentStats() for r in roster],
            attendance_threshold=settings.attendance_threshold_percent,
            low_below=low_threshold(scale, settings.low_grade_percent),
        )
        rows = [{"student": r["id"], "full_name": r["full_name"], **r["stats"]} for r in roster]
        data = {
            "course": {
                "id": course.pk,
                "group_name": course.group.name,
                "subject_name": course.subject.name,
                "teacher_name": course.teacher.full_name,
                "scale": scale,
            },
            "first": first,
            "last": last,
            "rows": rows,
            "summary": summary.as_dict(),
        }
        if kind := export_kind(request):
            header = [
                "№",
                "ФИО",
                "Средний балл",
                "Оценок",
                "Посещаемость, %",
                "Пропуски",
                "Уважительные",
                "Опоздания",
            ]
            table = [header] + [
                [
                    i,
                    r["full_name"],
                    _decimal(r["average"]),
                    r["grades"],
                    _decimal(r["attendance_percent"]),
                    r["absent"],
                    r["excused"],
                    r["late"],
                ]
                for i, r in enumerate(rows, start=1)
            ]
            title = f"{course.group.name} · {course.subject.name}"
            return _file(request, kind, f"vedomost-{first}-{last}", [(title, table)])
        return Response(s.CourseStatementSerializer(data).data)


def _decimal(value: Any) -> Any:
    return float(value) if value is not None else None


# --- Administrator: performance and attendance ----------------------------------------------


class PerformanceReportView(APIView):
    """Courses of the current year by group / subject / period; with a group — the student ×
    subject table as well (SPEC §8.8)."""

    permission_classes = (IsAdmin,)
    throttle_scope = "export"

    @extend_schema(
        parameters=[
            OpenApiParameter("group", str),
            OpenApiParameter("subject", str),
            *PERIOD_PARAMS,
        ],
        responses=s.PerformanceSerializer,
    )
    def get(self, request: Request) -> Response | HttpResponse:
        year = current_year()
        first, last = report_period(request, year)
        settings = CenterSettings.load()
        low_below = low_threshold(year.grade_scale, settings.low_grade_percent)
        courses = Course.objects.filter(group__academic_year=year).select_related(
            "group", "subject", "teacher"
        )
        group_id = uuid_param(request, "group")
        if group_id:
            courses = courses.filter(group__pk=group_id)
        if subject_id := uuid_param(request, "subject"):
            courses = courses.filter(subject__pk=subject_id)
        course_rows = []
        cells: dict[Any, dict[Any, StudentStats]] = {}
        for course in courses.order_by("group__name", "subject__name"):
            students = members_in(course, first, last)
            stats = course_stats(course, first, last, students=students)
            cells[course.pk] = stats
            summary = summarise_group(
                [stats.get(sid) or StudentStats() for sid in students],
                attendance_threshold=settings.attendance_threshold_percent,
                low_below=low_below,
            )
            course_rows.append(
                {
                    "course": course.pk,
                    "group_name": course.group.name,
                    "subject_name": course.subject.name,
                    "teacher_name": course.teacher.short_name,
                    **summary.as_dict(),
                }
            )
        student_rows: list[dict[str, Any]] = []
        if group_id:
            people = (
                GroupMembership.objects.filter(group_id=group_id, joined_on__lte=last)
                .filter(Q(left_on__isnull=True) | Q(left_on__gte=first))
                .select_related("student")
                .order_by("student__last_name", "student__first_name")
            )
            seen: set[Any] = set()
            for m in people:
                if m.student_id in seen:
                    continue
                seen.add(m.student_id)
                own = [
                    cells[row["course"]].get(m.student_id) or StudentStats() for row in course_rows
                ]
                student_rows.append(
                    {
                        "student": m.student_id,
                        "full_name": m.student.full_name,
                        "cells": [
                            {
                                "course": row["course"],
                                "average": st.average,
                                "attendance_percent": st.attendance_percent,
                            }
                            for row, st in zip(course_rows, own, strict=True)
                        ],
                    }
                )
        data = {"first": first, "last": last, "courses": course_rows, "students": student_rows}
        if kind := export_kind(request):
            header = [
                "Группа",
                "Предмет",
                "Преподаватель",
                "Учеников",
                "Средний балл",
                "Посещаемость, %",
                "Ниже порога посещаемости",
                "Низкий средний",
            ]
            table = [header] + [
                [
                    r["group_name"],
                    r["subject_name"],
                    r["teacher_name"],
                    r["students"],
                    _decimal(r["average"]),
                    _decimal(r["attendance_percent"]),
                    r["low_attendance"],
                    r["low_average"],
                ]
                for r in course_rows
            ]
            sheets = [("Курсы", table)]
            if student_rows:
                head = ["ФИО"]
                for r in course_rows:
                    head += [f"{r['subject_name']}: средний", f"{r['subject_name']}: посещ., %"]
                grid = [head]
                for st in student_rows:
                    line: list[Any] = [st["full_name"]]
                    for c in st["cells"]:
                        line += [_decimal(c["average"]), _decimal(c["attendance_percent"])]
                    grid.append(line)
                sheets.append(("Ученики", grid))
            return _file(request, kind, f"uspevaemost-{first}-{last}", sheets)
        return Response(s.PerformanceSerializer(data).data)


# --- Administrator: journal fill rate ------------------------------------------------------


class FillRateReportView(APIView):
    """How teachers fill the journal: lessons due by today, conducted, unfilled, no topic.
    A lesson counts for the teacher who taught it (a substitute included)."""

    permission_classes = (IsAdmin,)
    throttle_scope = "export"

    @extend_schema(parameters=PERIOD_PARAMS, responses=s.FillRateSerializer)
    def get(self, request: Request) -> Response | HttpResponse:
        year = current_year()
        first, last = report_period(request, year)
        day = journal.today()
        due = Lesson.objects.filter(
            course__group__academic_year=year,
            date__gte=first,
            date__lte=min(last, day - timedelta(days=1)),
        ).exclude(status=LessonStatus.CANCELLED)
        counts = (
            due.values("teacher_id")
            .annotate(
                due=Count("id"),
                conducted=Count("id", filter=Q(status=LessonStatus.CONDUCTED)),
                no_topic=Count("id", filter=Q(status=LessonStatus.CONDUCTED, topic="")),
                overdue=Count(
                    "id",
                    filter=Q(status=LessonStatus.PLANNED, date__lt=day - timedelta(days=2)),
                ),
            )
            .order_by()
        )
        teachers = User.objects.filter(pk__in=[c["teacher_id"] for c in counts])
        names = {u.pk: u.full_name for u in teachers}
        rows = []
        for c in counts:
            rows.append(
                {
                    "teacher": c["teacher_id"],
                    "teacher_name": names.get(c["teacher_id"], ""),
                    "due": c["due"],
                    "conducted": c["conducted"],
                    "unfilled": c["due"] - c["conducted"],
                    "overdue": c["overdue"],
                    "no_topic": c["no_topic"],
                    "filled_percent": percent(c["conducted"], c["due"]),
                }
            )
        rows.sort(key=lambda r: (r["filled_percent"] or 0, r["teacher_name"]))
        data = {"first": first, "last": last, "rows": rows}
        if kind := export_kind(request):
            header = [
                "Преподаватель",
                "Занятий к заполнению",
                "Проведено",
                "Не заполнено",
                "Старше 2 дней",
                "Без темы",
                "Заполнено, %",
            ]
            table = [header] + [
                [
                    r["teacher_name"],
                    r["due"],
                    r["conducted"],
                    r["unfilled"],
                    r["overdue"],
                    r["no_topic"],
                    _decimal(r["filled_percent"]),
                ]
                for r in rows
            ]
            return _file(request, kind, f"zapolnyaemost-{first}-{last}", [("Заполняемость", table)])
        return Response(s.FillRateSerializer(data).data)


# --- Administrator: the student's summary for parents --------------------------------------


class StudentSummaryView(APIView):
    """One printed sheet for parents: per subject — average, attendance, absences; the last
    mock exams against the goal (SPEC §8.8). JSON only: the browser prints it."""

    permission_classes = (IsAdmin,)

    @extend_schema(parameters=PERIOD_PARAMS[:3], responses=s.StudentSummarySerializer)
    def get(self, request: Request, pk: str) -> Response:
        student = get_object_or_404(User.objects.with_role(Role.STUDENT), pk=pk)
        year = current_year()
        first, last = report_period(request, year)
        memberships = (
            GroupMembership.objects.filter(student=student, group__academic_year=year)
            .filter(joined_on__lte=last)
            .filter(Q(left_on__isnull=True) | Q(left_on__gte=first))
            .select_related("group")
        )
        groups = sorted({m.group.name for m in memberships})
        courses = Course.objects.filter(group__in=[m.group_id for m in memberships]).select_related(
            "subject", "teacher", "group"
        )
        subjects = []
        for course in courses.order_by("subject__name"):
            st = course_stats(course, first, last, students=[student.pk]).get(student.pk)
            st = st or StudentStats()
            subjects.append(
                {
                    "subject_name": course.subject.name,
                    "teacher_name": course.teacher.short_name,
                    "group_name": course.group.name,
                    **st.as_dict(),
                }
            )
        targets = dict(
            StudentTarget.objects.filter(student=student).values_list("subject_id", "percent")
        )
        exams: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for result in (
            ExamResult.objects.filter(student=student, exam__date__gte=first, exam__date__lte=last)
            .select_related("exam__subject")
            .order_by("exam__date")
        ):
            exam = result.exam
            exams[exam.subject_id].append(
                {
                    "subject_name": exam.subject.name,
                    "title": exam.title,
                    "date": exam.date,
                    "total": result.total,
                    "max_score": exam.max_score,
                    "percent": percent(result.total, exam.max_score),
                    "was_absent": result.was_absent,
                    "target_percent": targets.get(exam.subject_id),
                }
            )
        exam_rows = [row for items in exams.values() for row in items[-3:]]
        exam_rows.sort(key=lambda r: (r["subject_name"], r["date"]))
        profile = getattr(student, "student_profile", None)
        data = {
            "student": {
                "id": student.pk,
                "full_name": student.full_name,
                "groups": groups,
                "parent_name": profile.parent_name if profile else "",
                "target": profile.target if profile else "",
            },
            "year_name": year.name,
            "scale": year.grade_scale,
            "first": first,
            "last": last,
            "subjects": subjects,
            "exams": exam_rows,
        }
        return Response(s.StudentSummarySerializer(data).data)
