"""Journal API for staff: grid, lesson page, writes, teacher's «Сегодня» (SPEC §7, §8.6)."""

from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import Course, GroupMembership, LessonType, Term, WorkType
from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin, IsTeacher
from apps.core.models import CenterSettings
from apps.core.params import date_param, uuid_param
from apps.schedule.models import Lesson, LessonStatus

from . import serializers as s
from . import services
from .models import Attendance, Grade
from .stats import StudentStats, course_stats, low_threshold

STAFF = (IsAdmin | IsTeacher,)


def courses_for(who: services.Actor) -> QuerySet[Course]:
    qs = Course.objects.select_related("group__academic_year", "subject", "teacher")
    return (
        qs if who.is_admin else qs.filter(Q(teacher=who.user) | Q(assistants=who.user)).distinct()
    )


def _course_info(course: Course) -> dict[str, Any]:
    return {
        "id": course.pk,
        "group_name": course.group.name,
        "subject_name": course.subject.name,
        "teacher_name": course.teacher.short_name,
        "year_name": course.group.academic_year.name,
        "scale": course.group.academic_year.grade_scale,
    }


def _rules(course: Course) -> dict[str, Any]:
    settings = CenterSettings.load()
    scale = course.group.academic_year.grade_scale
    return {
        "scale": scale,
        "low_below": low_threshold(scale, settings.low_grade_percent),
        "max_grades": settings.max_grades_per_lesson,
        "edit_window_days": settings.edit_window_days,
    }


def _lesson_row(lesson: Lesson, who: services.Actor) -> dict[str, Any]:
    state = services.editability(lesson, who)
    lesson_type: LessonType | None = lesson.lesson_type
    return {
        "id": lesson.pk,
        "date": lesson.date,
        "start_time": lesson.start_time,
        "lesson_type": lesson.lesson_type_id,
        "lesson_type_short": lesson_type.short if lesson_type else None,
        "lesson_type_name": lesson_type.name if lesson_type else None,
        "topic": lesson.topic,
        "homework": lesson.homework,
        "status": lesson.status,
        "version": lesson.version,
        "editable": state.editable,
        "needs_reason": state.needs_reason,
        "locked": state.locked,
    }


def _students(
    course: Course, first: date | None, last: date | None, stats: dict[Any, StudentStats]
) -> list[dict[str, Any]]:
    """Everyone who was in the group at some point of the period, with their periods."""
    qs = GroupMembership.objects.filter(group_id=course.group_id).select_related("student")
    if last is not None:
        qs = qs.filter(joined_on__lte=last)
    if first is not None:
        qs = qs.filter(Q(left_on__isnull=True) | Q(left_on__gte=first))
    people: dict[Any, dict[str, Any]] = {}
    for m in qs.order_by("student__last_name", "student__first_name", "joined_on"):
        row = people.setdefault(
            m.student_id,
            {
                "id": m.student_id,
                "short_name": m.student.short_name,
                "full_name": m.student.full_name,
                "periods": [],
                "stats": (stats.get(m.student_id) or StudentStats()).as_dict(),
            },
        )
        row["periods"].append({"start": m.joined_on, "end": m.left_on})
    return list(people.values())


def _period(request: Request, course: Course) -> tuple[date, date]:
    """?term= or ?from=&to=; default — the term containing today, else the whole year."""
    year = course.group.academic_year
    if term_id := uuid_param(request, "term"):
        term = get_object_or_404(Term, pk=term_id, year=year)
        return term.starts_on, term.ends_on
    first, last = date_param(request, "from"), date_param(request, "to")
    if first or last:
        return first or year.starts_on, last or year.ends_on
    day = services.today()
    current = Term.objects.filter(year=year, starts_on__lte=day, ends_on__gte=day).first()
    return (current.starts_on, current.ends_on) if current else (year.starts_on, year.ends_on)


class JournalCoursesView(APIView):
    """Courses for the journal picker: all for administrators, own for teachers."""

    permission_classes = STAFF

    @extend_schema(
        parameters=[OpenApiParameter("year", str)], responses=s.CourseOptionSerializer(many=True)
    )
    def get(self, request: Request) -> Response:
        who = services.actor(request)
        qs = courses_for(who)
        if year := uuid_param(request, "year"):
            qs = qs.filter(group__academic_year__pk=year)
        else:
            qs = qs.filter(group__academic_year__is_current=True)
        rows = [
            {
                "id": c.pk,
                "group_name": c.group.name,
                "subject_name": c.subject.name,
                "teacher_name": c.teacher.short_name,
                "year": c.group.academic_year_id,
            }
            for c in qs.filter(group__is_archived=False).order_by("group__name", "subject__name")
        ]
        return Response(s.CourseOptionSerializer(rows, many=True).data)


class JournalTermsView(APIView):
    permission_classes = STAFF

    @extend_schema(responses=s.TermOptionSerializer(many=True))
    def get(self, request: Request, pk: str) -> Response:
        course = get_object_or_404(courses_for(services.actor(request)), pk=pk)
        terms = Term.objects.filter(year=course.group.academic_year).order_by("starts_on")
        return Response(s.TermOptionSerializer(terms, many=True).data)


class JournalGridView(APIView):
    """The journal grid of one course (SPEC §7.3). A fixed number of queries."""

    permission_classes = STAFF

    @extend_schema(
        parameters=[
            OpenApiParameter("term", str),
            OpenApiParameter("from", str),
            OpenApiParameter("to", str),
        ],
        responses=s.GridSerializer,
    )
    def get(self, request: Request, pk: str) -> Response:
        who = services.actor(request)
        course = get_object_or_404(courses_for(who), pk=pk)
        first, last = _period(request, course)
        lessons = list(
            Lesson.objects.filter(course=course, date__range=(first, last))
            .exclude(status=LessonStatus.CANCELLED)
            .select_related("lesson_type")
            .order_by("date", "start_time")
        )
        lesson_ids = [lesson.pk for lesson in lessons]
        stats = course_stats(course, first, last)
        data = {
            "course": _course_info(course),
            "period_from": first,
            "period_to": last,
            "today": services.today(),
            "rules": _rules(course),
            "lessons": [_lesson_row(lesson, who) for lesson in lessons],
            "students": _students(course, first, last, stats),
            "attendance": Attendance.objects.filter(lesson_id__in=lesson_ids),
            "grades": Grade.objects.alive()
            .filter(lesson_id__in=lesson_ids)
            .select_related("created_by"),
            "work_types": WorkType.objects.filter(is_archived=False),
        }
        return Response(s.GridSerializer(data, context={"user_id": who.user.pk}).data)


def lesson_page(request: Request, lesson_id: Any) -> dict[str, Any]:
    who = services.actor(request)
    lesson = get_object_or_404(
        services.lessons_for(who).select_related(
            "course__group__academic_year", "course__subject", "course__teacher",
            "lesson_type", "room", "teacher",
        ),
        pk=lesson_id,
    )  # fmt: skip
    course = lesson.course
    stats = course_stats(course, lesson.date, lesson.date)
    students = [
        {
            "id": u.pk,
            "short_name": u.short_name,
            "full_name": u.full_name,
            "periods": [],
            "stats": (stats.get(u.pk) or StudentStats()).as_dict(),
        }
        for u in services.members(lesson)
    ]
    return {
        "course": _course_info(course),
        "today": services.today(),
        "rules": _rules(course),
        "lesson": _lesson_row(lesson, who),
        "comment": lesson.comment,
        "end_time": lesson.end_time,
        "room_name": lesson.room.name if lesson.room else None,
        "teacher_name": lesson.teacher.short_name,
        "window_closes_on": services.window_closes_on(lesson),
        "students": students,
        "attendance": Attendance.objects.filter(lesson=lesson),
        "grades": Grade.objects.alive().filter(lesson=lesson).select_related("created_by"),
        "work_types": WorkType.objects.filter(is_archived=False),
        "lesson_types": LessonType.objects.filter(is_archived=False),
        "topic_suggestions": services.topic_suggestions(lesson),
    }


def _page_response(request: Request, lesson_id: Any) -> Response:
    data = lesson_page(request, lesson_id)
    user = services.actor(request).user
    return Response(s.LessonPageSerializer(data, context={"user_id": user.pk}).data)


class LessonPageView(APIView):
    """The lesson page (SPEC §7.2): header, students on the date, attendance and grades."""

    permission_classes = STAFF

    @extend_schema(responses=s.LessonPageSerializer)
    def get(self, request: Request, pk: str) -> Response:
        return _page_response(request, pk)

    @extend_schema(request=s.LessonUpdateSerializer, responses=s.LessonPageSerializer)
    def patch(self, request: Request, pk: str) -> Response:
        form = s.LessonUpdateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = dict(form.validated_data)
        version, reason = data.pop("version"), data.pop("reason", "")
        services.update_lesson(request, pk, version, data, reason)
        return _page_response(request, pk)


class LessonConductView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.VersionReasonSerializer, responses=s.LessonPageSerializer)
    def post(self, request: Request, pk: str) -> Response:
        form = s.VersionReasonSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        services.conduct(request, pk, form.validated_data["version"], form.validated_data["reason"])
        return _page_response(request, pk)


class AttendanceView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.AttendanceWriteSerializer, responses=s.AttendanceSerializer)
    def put(self, request: Request, pk: str, student_id: str) -> Response:
        form = s.AttendanceWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        record = services.set_attendance(
            request, pk, student_id, data, data.get("version"), data["reason"]
        )
        return Response(s.AttendanceSerializer(record).data)


class AllPresentView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.ReasonMixin, responses=s.AttendanceSerializer(many=True))
    def post(self, request: Request, pk: str) -> Response:
        form = s.ReasonMixin(data=request.data)
        form.is_valid(raise_exception=True)
        records = services.mark_all_present(request, pk, form.validated_data["reason"])
        return Response(s.AttendanceSerializer(records, many=True).data)


class GradeCreateView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.GradeCreateSerializer, responses={201: s.GradeSerializer})
    def post(self, request: Request, pk: str) -> Response:
        form = s.GradeCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        grade = services.add_grade(request, pk, form.validated_data, form.validated_data["reason"])
        user = services.actor(request).user
        return Response(s.GradeSerializer(grade, context={"user_id": user.pk}).data, status=201)


class GradeView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.GradeUpdateSerializer, responses=s.GradeSerializer)
    def patch(self, request: Request, pk: str) -> Response:
        form = s.GradeUpdateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = dict(form.validated_data)
        version, reason = data.pop("version"), data.pop("reason", "")
        grade = services.update_grade(request, pk, version, data, reason)
        user = services.actor(request).user
        return Response(s.GradeSerializer(grade, context={"user_id": user.pk}).data)


class GradeDeleteView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.VersionReasonSerializer, responses=s.GradeSerializer)
    def post(self, request: Request, pk: str) -> Response:
        form = s.VersionReasonSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        grade = services.delete_grade(
            request, pk, form.validated_data["version"], form.validated_data["reason"]
        )
        return Response(s.GradeSerializer(grade, context={"user_id": grade.created_by_id}).data)


class GradeRestoreView(APIView):
    permission_classes = STAFF

    @extend_schema(request=s.VersionReasonSerializer, responses=s.GradeSerializer)
    def post(self, request: Request, pk: str) -> Response:
        form = s.VersionReasonSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        grade = services.restore_grade(
            request, pk, form.validated_data["version"], form.validated_data["reason"]
        )
        return Response(s.GradeSerializer(grade, context={"user_id": grade.created_by_id}).data)


# --- Teacher's «Сегодня» -------------------------------------------------------------------


def _today_row(lesson: Lesson, state: str) -> dict[str, Any]:
    return {
        "id": lesson.pk,
        "date": lesson.date,
        "start_time": lesson.start_time,
        "end_time": lesson.end_time,
        "group_name": lesson.course.group.name,
        "subject_name": lesson.course.subject.name,
        "room_name": lesson.room.name if lesson.room else None,
        "status": lesson.status,
        "state": state,
        "is_substituted": lesson.teacher_id != lesson.course.teacher_id,
    }


def _state(lesson: Lesson, now: datetime) -> str:
    if lesson.status == LessonStatus.CANCELLED:
        return "cancelled"
    if lesson.status == LessonStatus.CONDUCTED:
        return "filled"
    start = timezone.make_aware(datetime.combine(lesson.date, lesson.start_time))
    return "upcoming" if start > now else "to_fill"


class TeacherTodayView(APIView):
    """SPEC §7.1: today's lessons, unfilled past lessons, students needing attention."""

    permission_classes = (IsTeacher,)

    @extend_schema(responses=s.TodaySerializer)
    def get(self, request: Request) -> Response:
        who = services.actor(request)
        day = services.today()
        now = timezone.localtime()
        settings = CenterSettings.load()
        scoped = services.lessons_for(who).select_related(
            "course__group", "course__subject", "course__teacher", "room"
        )
        today_lessons = [
            _today_row(x, _state(x, now)) for x in scoped.filter(date=day).order_by("start_time")
        ]
        since = day - timedelta(days=settings.attendance_window_days)
        unfilled = [
            _today_row(x, "to_fill")
            for x in scoped.filter(
                date__gte=since, date__lte=day, status=LessonStatus.PLANNED
            ).order_by("-date", "-start_time")
            if _state(x, now) == "to_fill"
        ]
        return Response(
            s.TodaySerializer(
                {
                    "today": day,
                    "lessons": today_lessons,
                    "unfilled": unfilled,
                    "attention": self._attention(who, day, settings),
                }
            ).data
        )

    def _attention(
        self, who: services.Actor, day: date, settings: CenterSettings
    ) -> list[dict[str, Any]]:
        courses = list(
            courses_for(who).filter(group__is_archived=False, group__academic_year__is_current=True)
        )
        since = day - timedelta(days=settings.attendance_window_days - 1)
        names: dict[Any, None] = {}
        result = []
        for course in courses:
            stats = course_stats(course, since, day)
            threshold = low_threshold(
                course.group.academic_year.grade_scale, settings.low_grade_percent
            )
            recent: dict[Any, list[int]] = {}
            # Last two grades per student, newest first (one query per course).
            for sid, value in (
                Grade.objects.alive()
                .filter(lesson__course=course)
                .order_by("student_id", "-lesson__date", "-lesson__start_time", "-position")
                .values_list("student_id", "value")
            ):
                bucket = recent.setdefault(sid, [])
                if len(bucket) < 2:
                    bucket.append(value)
            members_now = set(
                GroupMembership.objects.filter(group_id=course.group_id)
                .filter(Q(left_on__isnull=True) | Q(left_on__gte=day), joined_on__lte=day)
                .values_list("student_id", flat=True)
            )
            for sid in members_now:
                st = stats.get(sid)
                low_attendance = (
                    st is not None
                    and st.attendance_percent is not None
                    and st.attendance_percent < settings.attendance_threshold_percent
                )
                last_two = recent.get(sid, [])
                two_low = len(last_two) == 2 and all(v < threshold for v in last_two)
                if not (low_attendance or two_low):
                    continue
                names.setdefault(sid, None)
                result.append(
                    {
                        "student": sid,
                        "course": course.pk,
                        "group_name": course.group.name,
                        "subject_name": course.subject.name,
                        "reason": "attendance" if low_attendance else "low_grades",
                        "attendance_percent": st.attendance_percent if st else None,
                        "grades": list(reversed(last_two)) if two_low else [],
                    }
                )
        people: dict[Any, str] = {u.pk: u.short_name for u in User.objects.filter(pk__in=names)}
        for row in result:
            row["student_name"] = people.get(row["student"], "")
        return sorted(result, key=lambda r: (r["student_name"], r["subject_name"]))
