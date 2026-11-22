"""The administrator's «Обзор» (SPEC §8.1): every block leads to an action."""

from datetime import datetime, timedelta
from typing import Any

from django.db.models import Count, Max, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import Course
from apps.accounts.models import LoginEvent, Role, User
from apps.accounts.permissions import IsAdmin
from apps.audit.models import AuditLog, DeniedRequest
from apps.audit.views import AuditLogSerializer
from apps.core.models import CenterSettings
from apps.journal import services as journal
from apps.journal.stats import course_stats
from apps.payments import services as payments
from apps.schedule.models import Lesson, LessonStatus

from .views import members_in

UNFILLED_AFTER_DAYS = 2
# A user refused this many times within an hour is probing ids, not misclicking.
DENIED_SPIKE_PER_HOUR = 10
NEW_DEVICE_DAYS = 7
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


class DeniedUserSerializer(serializers.Serializer[Any]):
    user = serializers.UUIDField()
    full_name = serializers.CharField()
    count = serializers.IntegerField()
    last_hour = serializers.IntegerField()
    spike = serializers.BooleanField()
    last_at = serializers.DateTimeField()


class AdminDeviceLoginSerializer(serializers.Serializer[Any]):
    user = serializers.UUIDField()
    full_name = serializers.CharField()
    at = serializers.DateTimeField()
    ip = serializers.CharField(allow_null=True)
    user_agent = serializers.CharField(allow_blank=True)


class DebtSerializer(serializers.Serializer[Any]):
    debtors = serializers.IntegerField()
    total = serializers.IntegerField()


class OverviewSerializer(serializers.Serializer[Any]):
    today = serializers.DateField()
    lessons = OverviewTodaySerializer()
    unfilled = UnfilledTeacherSerializer(many=True)
    low_attendance = LowAttendanceSerializer(many=True)
    attendance_threshold = serializers.IntegerField()
    attendance_window_days = serializers.IntegerField()
    blocked_logins = BlockedLoginSerializer(many=True)
    failed_logins_24h = serializers.IntegerField()
    denied = DeniedUserSerializer(many=True)
    admin_new_devices = AdminDeviceLoginSerializer(many=True)
    audit = AuditLogSerializer(many=True)
    debt = DebtSerializer()


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
            "denied": self._denied(now),
            "admin_new_devices": self._admin_new_devices(now),
            "audit": AuditLog.objects.select_related("actor")[:20],
            "debt": self._debt(),
        }
        return Response(OverviewSerializer(data).data)

    def _debt(self) -> dict[str, int]:
        """Stage 12: how many students owe and how much, from the one balance function."""
        students = list(User.objects.with_role(Role.STUDENT).values_list("pk", flat=True))
        debts = [b.debt for b in payments.balances(students).values() if b.debt > 0]
        return {"debtors": len(debts), "total": sum(debts)}

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

    def _denied(self, now: datetime) -> list[dict[str, Any]]:
        """Users refused access (403 / «not found») in the last 24 hours, spikes first."""
        hour_ago = now - timedelta(hours=1)
        rows = (
            DeniedRequest.objects.filter(at__gte=now - timedelta(hours=24))
            .values("user_id")
            .annotate(
                count=Count("id"),
                last_hour=Count("id", filter=Q(at__gte=hour_ago)),
                last_at=Max("at"),
            )
            .order_by("-last_hour", "-count")[:10]
        )
        names = {
            u.pk: u.full_name for u in User.objects.filter(pk__in=[r["user_id"] for r in rows])
        }
        return [
            {
                "user": r["user_id"],
                "full_name": names.get(r["user_id"], ""),
                "count": r["count"],
                "last_hour": r["last_hour"],
                "spike": r["last_hour"] >= DENIED_SPIKE_PER_HOUR,
                "last_at": r["last_at"],
            }
            for r in rows
        ]

    def _admin_new_devices(self, now: datetime) -> list[dict[str, Any]]:
        """Administrators' successful logins from a browser/app never used by them before."""
        since = now - timedelta(days=NEW_DEVICE_DAYS)
        admins = User.objects.with_role(Role.ADMIN)
        recent = (
            LoginEvent.objects.filter(success=True, at__gte=since, user__in=admins)
            .select_related("user")
            .order_by("at")
        )
        result = []
        for event in recent:
            if event.user is None:
                continue
            seen_before = LoginEvent.objects.filter(
                success=True, user=event.user, user_agent=event.user_agent, at__lt=event.at
            ).exists()
            if not seen_before:
                result.append(
                    {
                        "user": event.user_id,
                        "full_name": event.user.full_name,
                        "at": event.at,
                        "ip": event.ip,
                        "user_agent": event.user_agent,
                    }
                )
        return list(reversed(result))[:20]
