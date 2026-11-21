"""The administrator's «Обзор» (SPEC §8.1): every block leads to an action."""

from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Max
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import Course
from apps.accounts.models import LoginEvent, User
from apps.accounts.permissions import IsAdmin
from apps.audit.models import AuditLog
from apps.audit.views import AuditLogSerializer
from apps.core.models import CenterSettings
from apps.journal import services as journal
from apps.journal.stats import course_stats
from apps.schedule.models import Lesson, LessonStatus

from .views import members_in

UNFILLED_AFTER_DAYS = 2
BLOCKING = (
    LoginEvent.Reason.LOCKED,
    LoginEvent.Reason.IP_LIMIT,
    LoginEvent.Reason.TOTP_LIMIT,
)


class OverviewTodaySerializer(serializers.Serializer[Any]):
    total = serializers.IntegerField()
    conducted = serializers.IntegerField()
    to_fill = serializers.IntegerField()
    cancelled = serializers.IntegerField()


class UnfilledLessonSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    date = serializers.DateField()
    group_name = serializers.CharField()
    subject_name = serializers.CharField()


class UnfilledTeacherSerializer(serializers.Serializer[Any]):
    teacher = serializers.UUIDField()
    teacher_name = serializers.CharField()
    count = serializers.IntegerField()
    lessons = UnfilledLessonSerializer(many=True)


class LowAttendanceSerializer(serializers.Serializer[Any]):
    student = serializers.UUIDField()
    full_name = serializers.CharField()
    course = serializers.UUIDField()
    group_name = serializers.CharField()
    subject_name = serializers.CharField()
    attendance_percent = serializers.DecimalField(max_digits=5, decimal_places=2)


class BlockedLoginSerializer(serializers.Serializer[Any]):
    login = serializers.CharField()
    attempts = serializers.IntegerField()
    last_at = serializers.DateTimeField()


class OverviewSerializer(serializers.Serializer[Any]):
    today = serializers.DateField()
    lessons = OverviewTodaySerializer()
    unfilled = UnfilledTeacherSerializer(many=True)
    low_attendance = LowAttendanceSerializer(many=True)
    attendance_threshold = serializers.IntegerField()
    attendance_window_days = serializers.IntegerField()
    blocked_logins = BlockedLoginSerializer(many=True)
    failed_logins_24h = serializers.IntegerField()
    audit = AuditLogSerializer(many=True)


class OverviewView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(responses=OverviewSerializer)
    def get(self, request: Request) -> Response:
        day = journal.today()
        settings = CenterSettings.load()
        now = timezone.localtime()
        data = {
            "today": day,
            "lessons": self._today(day, now),
            "unfilled": self._unfilled(day),
            "low_attendance": self._low_attendance(day, settings),
            "attendance_threshold": settings.attendance_threshold_percent,
            "attendance_window_days": settings.attendance_window_days,
            "blocked_logins": self._blocked(now),
            "failed_logins_24h": LoginEvent.objects.filter(
                at__gte=now - timedelta(hours=24), success=False
            ).count(),
            "audit": AuditLog.objects.select_related("actor")[:20],
        }
        return Response(OverviewSerializer(data).data)

    def _today(self, day: Any, now: datetime) -> dict[str, int]:
        lessons = list(Lesson.objects.filter(date=day).values_list("status", "start_time"))
        started = now.time()
        return {
            "total": sum(1 for s, _ in lessons if s != LessonStatus.CANCELLED),
            "conducted": sum(1 for s, _ in lessons if s == LessonStatus.CONDUCTED),
            "to_fill": sum(1 for s, t in lessons if s == LessonStatus.PLANNED and t <= started),
            "cancelled": sum(1 for s, _ in lessons if s == LessonStatus.CANCELLED),
        }

    def _unfilled(self, day: Any) -> list[dict[str, Any]]:
        """Planned lessons older than 2 days of the current year, grouped by the teacher."""
        lessons = (
            Lesson.objects.filter(
                status=LessonStatus.PLANNED,
                date__lt=day - timedelta(days=UNFILLED_AFTER_DAYS),
                course__group__academic_year__is_current=True,
            )
            .select_related("teacher", "course__group", "course__subject")
            .order_by("date", "start_time")
        )
        teachers: dict[Any, dict[str, Any]] = {}
        for lesson in lessons:
            row = teachers.setdefault(
                lesson.teacher_id,
                {
                    "teacher": lesson.teacher_id,
                    "teacher_name": lesson.teacher.full_name,
                    "count": 0,
                    "lessons": [],
                },
            )
            row["count"] += 1
            if len(row["lessons"]) < 5:
                row["lessons"].append(
                    {
                        "id": lesson.pk,
                        "date": lesson.date,
                        "group_name": lesson.course.group.name,
                        "subject_name": lesson.course.subject.name,
                    }
                )
        return sorted(teachers.values(), key=lambda r: (-r["count"], r["teacher_name"]))

    def _low_attendance(self, day: Any, settings: CenterSettings) -> list[dict[str, Any]]:
        since = day - timedelta(days=settings.attendance_window_days - 1)
        courses = Course.objects.filter(
            group__academic_year__is_current=True, group__is_archived=False
        ).select_related("group", "subject")
        rows = []
        names: dict[Any, str] = {}
        for course in courses:
            current = members_in(course, day, day)
            stats = course_stats(course, since, day, students=current)
            for sid, st in stats.items():
                pct = st.attendance_percent
                if pct is not None and pct < settings.attendance_threshold_percent:
                    rows.append(
                        {
                            "student": sid,
                            "course": course.pk,
                            "group_name": course.group.name,
                            "subject_name": course.subject.name,
                            "attendance_percent": pct,
                        }
                    )
                    names[sid] = ""
        for user in User.objects.filter(pk__in=list(names)):
            names[user.pk] = user.full_name
        for row in rows:
            row["full_name"] = names[row["student"]]
        rows.sort(key=lambda r: (r["attendance_percent"], r["full_name"]))
        return rows[:50]

    def _blocked(self, now: datetime) -> list[dict[str, Any]]:
        return [
            {"login": r["login_attempted"], "attempts": r["attempts"], "last_at": r["last_at"]}
            for r in LoginEvent.objects.filter(
                at__gte=now - timedelta(hours=24), reason__in=BLOCKING
            )
            .values("login_attempted")
            .annotate(attempts=Count("id"), last_at=Max("at"))
            .order_by("-last_at")[:20]
        ]
