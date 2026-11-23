"""Administrator: years, terms, catalogs, groups and their composition, courses."""

from datetime import timedelta
from typing import Any, ClassVar

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.permissions import IsAdmin, require_recent_password
from apps.audit import services as audit
from apps.core.params import uuid_param
from apps.core.viewsets import AuditedAdminViewSet
from apps.schedule import services as schedule

from . import serializers as s
from .models import (
    AcademicYear,
    Course,
    Group,
    GroupMembership,
    Holiday,
    LessonType,
    Room,
    Subject,
    Term,
    WorkType,
)


def _membership_snapshot(m: GroupMembership) -> dict[str, Any]:
    return {
        "group": str(m.group_id),
        "student": str(m.student_id),
        "joined_on": m.joined_on.isoformat(),
        "left_on": m.left_on.isoformat() if m.left_on else None,
    }


def _memberships() -> QuerySet[GroupMembership]:
    return GroupMembership.objects.select_related("group", "student")


class AcademicYearViewSet(AuditedAdminViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = s.AcademicYearSerializer
    pagination_class = None
    audit_name = "academic_year"
    integrity_error = "years_overlap"
    constraint_codes: ClassVar = {"name": "name_taken", "one_current": "current_year_exists"}

    def perform_update(self, serializer: Any) -> None:
        # Changing the grade scale is a dangerous action: fresh password needed.
        new_scale = serializer.validated_data.get("grade_scale")
        if new_scale is not None and new_scale != serializer.instance.grade_scale:
            require_recent_password(self.request)
        super().perform_update(serializer)


class TermViewSet(AuditedAdminViewSet):
    serializer_class = s.TermSerializer
    pagination_class = None
    audit_name = "term"
    integrity_error = "terms_overlap"
    constraint_codes: ClassVar = {"term_name": "name_taken"}

    def get_queryset(self) -> QuerySet[Term]:
        qs = Term.objects.select_related("year")
        if year := uuid_param(self.request, "year"):
            qs = qs.filter(year__pk=year)
        return qs

    @extend_schema(parameters=[OpenApiParameter("year", str)])
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)


class SubjectViewSet(AuditedAdminViewSet):
    queryset = Subject.objects.all()
    serializer_class = s.SubjectSerializer
    pagination_class = None
    audit_name = "subject"
    integrity_error = "name_taken"


class RoomViewSet(AuditedAdminViewSet):
    queryset = Room.objects.all()
    serializer_class = s.RoomSerializer
    pagination_class = None
    audit_name = "room"
    integrity_error = "name_taken"


class WorkTypeViewSet(AuditedAdminViewSet):
    queryset = WorkType.objects.all()
    serializer_class = s.WorkTypeSerializer
    pagination_class = None
    audit_name = "work_type"
    integrity_error = "name_taken"


class LessonTypeViewSet(AuditedAdminViewSet):
    queryset = LessonType.objects.all()
    serializer_class = s.LessonTypeSerializer
    pagination_class = None
    audit_name = "lesson_type"
    integrity_error = "name_taken"


class HolidayViewSet(AuditedAdminViewSet):
    queryset = Holiday.objects.all()
    serializer_class = s.HolidaySerializer
    pagination_class = None
    audit_name = "holiday"
    integrity_error = "date_taken"

    def after_create(self, instance: Holiday) -> None:
        schedule.remove_generated_on(instance.date)

    def after_destroy(self, instance: Holiday) -> None:
        schedule.generate_lessons()


class GroupViewSet(AuditedAdminViewSet):
    serializer_class = s.GroupSerializer
    pagination_class = None
    audit_name = "group"
    integrity_error = "name_taken"

    def get_queryset(self) -> QuerySet[Group]:
        qs: QuerySet[Group] = s.with_members_count(
            Group.objects.select_related("academic_year").prefetch_related(
                "courses__subject", "courses__teacher"
            )
        )
        if year := uuid_param(self.request, "year"):
            qs = qs.filter(academic_year__pk=year)
        if self.request.query_params.get("archived") != "true":
            qs = qs.filter(is_archived=False)
        return qs

    @extend_schema(parameters=[OpenApiParameter("year", str), OpenApiParameter("archived", bool)])
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    def get_object(self) -> Group:
        # Archived groups stay reachable by id.
        qs: QuerySet[Group] = s.with_members_count(Group.objects.select_related("academic_year"))
        return get_object_or_404(qs, pk=self.kwargs["pk"])

    def after_update(self, instance: Group, previous: Group) -> None:
        if instance.is_archived and not previous.is_archived:
            schedule.remove_future_generated(instance.courses.values_list("pk", flat=True))
        if previous.is_archived and not instance.is_archived:
            schedule.generate_lessons()

    @extend_schema(responses=s.MembershipSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request: Request, pk: str) -> Response:
        """Full history of the composition: current and former members."""
        group = self.get_object()
        qs = (
            GroupMembership.objects.filter(group=group)
            .select_related("student", "group")
            .order_by("student__last_name", "student__first_name", "joined_on")
        )
        return Response(s.MembershipSerializer(qs, many=True).data)

    @extend_schema(request=s.AddMemberSerializer, responses={201: s.MembershipSerializer})
    @members.mapping.post
    def add_member(self, request: Request, pk: str) -> Response:
        group = self.get_object()
        form = s.AddMemberSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        if group.is_archived:
            raise ValidationError({"group": ["group_archived"]})
        try:
            with transaction.atomic():
                membership = GroupMembership.objects.create(group=group, **form.validated_data)
                audit.record(
                    request=request,
                    action="group.member_add",
                    entity=membership,
                    after=_membership_snapshot(membership),
                )
        except IntegrityError as exc:
            raise ValidationError({"student": ["already_member"]}) from exc
        return Response(s.MembershipSerializer(membership).data, status=201)


class MembershipView(APIView):
    """PATCH: fix dates of a membership. Every change is audited."""

    permission_classes = (IsAdmin,)

    @extend_schema(request=s.MembershipSerializer, responses=s.MembershipSerializer)
    def patch(self, request: Request, pk: str) -> Response:
        membership = get_object_or_404(
            GroupMembership.objects.select_related("group", "student"), pk=pk
        )
        before = _membership_snapshot(membership)
        form = s.MembershipSerializer(membership, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                membership = form.save()
                audit.record(
                    request=request,
                    action="group.member_update",
                    entity=membership,
                    before=before,
                    after=_membership_snapshot(membership),
                )
        except IntegrityError as exc:
            raise ValidationError({"joined_on": ["periods_overlap"]}) from exc
        return Response(s.MembershipSerializer(membership).data)


class MembershipLeaveView(APIView):
    """Exclude from the group: the membership ends on `left_on` (inclusive)."""

    permission_classes = (IsAdmin,)

    @extend_schema(request=s.LeaveSerializer, responses=s.MembershipSerializer)
    def post(self, request: Request, pk: str) -> Response:
        membership = get_object_or_404(
            GroupMembership.objects.select_related("group", "student"), pk=pk
        )
        form = s.LeaveSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        left_on = form.validated_data["left_on"]
        if left_on < membership.joined_on:
            raise ValidationError({"left_on": ["left_before_joined"]})
        before = _membership_snapshot(membership)
        with transaction.atomic():
            membership.left_on = left_on
            membership.save(update_fields=["left_on"])
            audit.record(
                request=request,
                action="group.member_leave",
                entity=membership,
                before=before,
                after=_membership_snapshot(membership),
            )
        return Response(s.MembershipSerializer(membership).data)


class MembershipTransferView(APIView):
    """Transfer: the old membership ends the day before `date`, a new one starts
    on `date`. Old grades stay in the old course."""

    permission_classes = (IsAdmin,)

    @extend_schema(request=s.TransferSerializer, responses={201: s.MembershipSerializer})
    def post(self, request: Request, pk: str) -> Response:
        membership = get_object_or_404(
            GroupMembership.objects.select_related("group", "student"), pk=pk
        )
        form = s.TransferSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        target: Group = form.validated_data["group"]
        day = form.validated_data["date"]
        if target.pk == membership.group_id:
            raise ValidationError({"group": ["same_group"]})
        if day <= membership.joined_on:
            raise ValidationError({"date": ["transfer_before_join"]})
        if membership.left_on is not None and membership.left_on < day - timedelta(days=1):
            raise ValidationError({"date": ["membership_already_ended"]})
        before = _membership_snapshot(membership)
        try:
            with transaction.atomic():
                membership.left_on = day - timedelta(days=1)
                membership.save(update_fields=["left_on"])
                new = GroupMembership.objects.create(
                    group=target, student=membership.student, joined_on=day
                )
                audit.record(
                    request=request,
                    action="group.member_transfer",
                    entity=membership,
                    before=before,
                    after={
                        "closed": _membership_snapshot(membership),
                        "opened": _membership_snapshot(new),
                    },
                )
        except IntegrityError as exc:
            raise ValidationError({"group": ["already_member"]}) from exc
        return Response(s.MembershipSerializer(new).data, status=201)


class CourseViewSet(AuditedAdminViewSet):
    serializer_class = s.CourseSerializer
    pagination_class = None
    audit_name = "course"
    integrity_error = "course_exists"

    def get_queryset(self) -> QuerySet[Course]:
        qs = Course.objects.select_related("group", "subject", "teacher").prefetch_related(
            "assistants"
        )
        if group := uuid_param(self.request, "group"):
            qs = qs.filter(group__pk=group)
        if teacher := uuid_param(self.request, "teacher"):
            qs = qs.filter(Q(teacher__pk=teacher) | Q(assistants__pk=teacher)).distinct()
        if year := uuid_param(self.request, "year"):
            qs = qs.filter(group__academic_year__pk=year)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("group", str),
            OpenApiParameter("teacher", str),
            OpenApiParameter("year", str),
        ]
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    def snapshot(self, instance: Course) -> dict[str, Any]:  # type: ignore[override]
        data = super().snapshot(instance)
        data["assistants"] = sorted(
            str(pk) for pk in instance.assistants.values_list("pk", flat=True)
        )
        return data

    def after_update(self, instance: Course, previous: Course) -> None:
        if instance.teacher_id != previous.teacher_id:
            schedule.reassign_future_lessons(instance, previous.teacher_id)


class TeacherOptionsView(APIView):
    """Active teachers for selects in admin forms."""

    permission_classes = (IsAdmin,)

    @extend_schema(
        parameters=[OpenApiParameter("subject", str)],
        responses=s.PersonSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        qs = User.objects.with_role(Role.TEACHER).active().order_by("last_name", "first_name")
        # Stage 19: only those who teach the chosen subject (a course's teacher list).
        subject = uuid_param(request, "subject")
        if subject is not None:
            qs = qs.filter(teacher_profile__subjects=subject)
        return Response(s.PersonSerializer(qs, many=True).data)
