"""Schedule API: template (slots), lessons and exceptions, teacher requests, views per role."""

from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import Course, Room
from apps.accounts.models import User
from apps.accounts.permissions import (
    STUDENT_PAGES,
    IsAdmin,
    IsTeacher,
    active_role,
    current_user,
    subject_student,
)
from apps.audit import services as audit
from apps.core.params import date_param, time_param, uuid_param

from . import services
from .models import Lesson, LessonStatus, ScheduleRequest, ScheduleSlot
from .serializers import (
    CancelSerializer,
    ExtraLessonSerializer,
    LessonSerializer,
    MoveSerializer,
    ResolveSerializer,
    RoomOptionSerializer,
    ScheduleRequestSerializer,
    SlotSerializer,
    SlotWriteSerializer,
    StudentLessonSerializer,
    SubstituteSerializer,
    VersionSerializer,
)

MAX_RANGE_DAYS = 62
LESSON_AUDIT_FIELDS = (
    "date",
    "start_time",
    "end_time",
    "room_id",
    "teacher_id",
    "status",
    "cancel_reason",
    "lesson_type_id",
)
SLOT_AUDIT_FIELDS = (
    "course_id",
    "weekday",
    "start_time",
    "end_time",
    "room_id",
    "lesson_type_id",
    "valid_from",
    "valid_to",
)

Warnings = list[dict[str, Any]]

RANGE_PARAMS = [OpenApiParameter("from", str), OpenApiParameter("to", str)]


def lesson_queryset(base: QuerySet[Lesson] | None = None) -> QuerySet[Lesson]:
    return (base if base is not None else Lesson.objects.all()).select_related(
        "course__group",
        "course__subject",
        "course__teacher",
        "teacher",
        "room",
        "planned_room",
        "lesson_type",
    )


def date_range(request: Request) -> tuple[date, date]:
    """?from=&to= (inclusive); default — the current week Monday..Sunday."""
    today = timezone.localdate()
    first = date_param(request, "from") or today - timedelta(days=today.isoweekday() - 1)
    last = date_param(request, "to") or first + timedelta(days=6)
    if last < first or (last - first).days >= MAX_RANGE_DAYS:
        raise ValidationError({"to": ["invalid_range"]})
    return first, last


def _lesson_snapshot(lesson: Lesson) -> dict[str, Any]:
    return audit.snapshot(lesson, LESSON_AUDIT_FIELDS)


def _slot_snapshot(slot: ScheduleSlot) -> dict[str, Any]:
    return audit.snapshot(slot, SLOT_AUDIT_FIELDS)


def _not_editable(lesson: Lesson) -> None:
    if lesson.status == LessonStatus.CONDUCTED:
        raise ValidationError({"detail": ["lesson_conducted"]})


ChangeResult = inline_serializer(
    "SlotChange",
    fields={
        "slot": SlotSerializer(allow_null=True),
        "plan": serializers.DictField(),
        "warnings": serializers.ListField(child=serializers.DictField()),
    },
)
LessonChange = inline_serializer(
    "LessonChange",
    fields={
        "lesson": LessonSerializer(),
        "warnings": serializers.ListField(child=serializers.DictField()),
    },
)


# --- Template ------------------------------------------------------------------------------


class AdminSlotViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,  # type: ignore[type-arg]
):
    """Week template. Changes apply only to future, untouched lessons, after the administrator
    confirms the list of affected dates."""

    permission_classes = (IsAdmin,)
    serializer_class = SlotSerializer
    pagination_class = None
    lookup_value_converter = "uuid"

    def get_queryset(self) -> QuerySet[ScheduleSlot]:
        qs = ScheduleSlot.objects.select_related(
            "course__group", "course__subject", "course__teacher", "room", "lesson_type"
        )
        request = self.request
        if group := uuid_param(request, "group"):
            qs = qs.filter(course__group__pk=group)
        if teacher := uuid_param(request, "teacher"):
            qs = qs.filter(course__teacher__pk=teacher)
        if room := uuid_param(request, "room"):
            qs = qs.filter(room__pk=room)
        if course := uuid_param(request, "course"):
            qs = qs.filter(course__pk=course)
        if day := date_param(request, "active_on"):
            qs = qs.filter(Q(valid_to__isnull=True) | Q(valid_to__gte=day), valid_from__lte=day)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("group", str),
            OpenApiParameter("teacher", str),
            OpenApiParameter("room", str),
            OpenApiParameter("course", str),
            OpenApiParameter("active_on", str),
        ]
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    def _spec(self, data: dict[str, Any], slot: ScheduleSlot | None) -> services.SlotSpec:
        def value(name: str) -> Any:
            if name in data:
                return data[name]
            return getattr(slot, name) if slot is not None else None

        return services.SlotSpec(
            course=value("course"),
            weekday=value("weekday"),
            start_time=value("start_time"),
            end_time=value("end_time"),
            room=value("room"),
            lesson_type=value("lesson_type"),
            valid_from=value("valid_from"),
            valid_to=value("valid_to"),
        )

    def _check(
        self, spec: services.SlotSpec, slot: ScheduleSlot | None
    ) -> tuple[services.SlotPlan, Warnings]:
        plan = services.plan_slot_change(slot, spec)
        recurring = services.check_slot_template(spec, exclude_slot_id=slot.pk if slot else None)
        conflicts, warnings = services.check_lessons(services.template_candidates(spec, plan))
        if recurring or conflicts:
            raise services.ScheduleConflict(recurring + conflicts)
        return plan, warnings

    @extend_schema(request=SlotWriteSerializer, responses={201: ChangeResult})
    def create(self, request: Request) -> Response:
        form = SlotWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = {k: v for k, v in form.validated_data.items() if k != "confirm"}
        spec = self._spec(data, None)
        plan, warnings = self._check(spec, None)
        with transaction.atomic():
            slot = ScheduleSlot.objects.create(**data)
            services.generate_lessons(slots=[slot])
            audit.record(
                request=request, action="slot.create", entity=slot, after=_slot_snapshot(slot)
            )
        slot = self.get_queryset().get(pk=slot.pk)
        return Response(
            {"slot": SlotSerializer(slot).data, "plan": plan.as_dict(), "warnings": warnings},
            status=201,
        )

    @extend_schema(request=SlotWriteSerializer, responses=ChangeResult)
    @action(detail=True, methods=["post"])
    def preview(self, request: Request, pk: str) -> Response:
        """What PATCH would do, without saving: affected dates, conflicts, warnings."""
        slot = self.get_object()
        form = SlotWriteSerializer(slot, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        plan, warnings = self._check(self._spec(form.validated_data, slot), slot)
        return Response(
            {"slot": SlotSerializer(slot).data, "plan": plan.as_dict(), "warnings": warnings}
        )

    @extend_schema(request=SlotWriteSerializer, responses=ChangeResult)
    def partial_update(self, request: Request, pk: str) -> Response:
        slot = self.get_object()
        form = SlotWriteSerializer(slot, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        data = {k: v for k, v in form.validated_data.items() if k != "confirm"}
        spec = self._spec(data, slot)
        plan, warnings = self._check(spec, slot)
        if plan.touches_existing and not form.validated_data.get("confirm"):
            raise services.ConfirmationRequired(plan.as_dict())
        before = _slot_snapshot(slot)
        with transaction.atomic():
            for name, value in data.items():
                setattr(slot, name, value)
            slot.save()
            services.apply_slot_change(slot, spec, plan)
            audit.record(
                request=request,
                action="slot.update",
                entity=slot,
                before=before,
                after={**_slot_snapshot(slot), "lessons": plan.as_dict()},
            )
        slot = self.get_queryset().get(pk=slot.pk)
        return Response(
            {"slot": SlotSerializer(slot).data, "plan": plan.as_dict(), "warnings": warnings}
        )

    @extend_schema(
        parameters=[OpenApiParameter("confirm", bool)], request=None, responses=ChangeResult
    )
    def destroy(self, request: Request, pk: str) -> Response:
        """Removes the slot: untouched future lessons go, past lessons and exceptions stay."""
        slot = self.get_object()
        plan = services.plan_slot_change(slot, None)
        if plan.touches_existing and request.query_params.get("confirm") != "true":
            raise services.ConfirmationRequired(plan.as_dict())
        before = _slot_snapshot(slot)
        with transaction.atomic():
            Lesson.objects.filter(pk__in=[lesson.pk for lesson in plan.remove]).delete()
            Lesson.objects.filter(slot=slot).update(slot=None)
            slot_id = slot.pk
            slot.delete()
            audit.record(
                request=request,
                action="slot.delete",
                entity_type="schedule.scheduleslot",
                entity_id=str(slot_id),
                before=before,
                after={"lessons": plan.as_dict()},
            )
        return Response({"slot": None, "plan": plan.as_dict(), "warnings": []})


# --- Lessons and exceptions ----------------------------------------------------------------


class AdminLessonViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,  # type: ignore[type-arg]
):
    """Concrete lessons and their exceptions: cancel, restore, move, substitute, extra lesson."""

    permission_classes = (IsAdmin,)
    serializer_class = LessonSerializer
    pagination_class = None
    lookup_value_converter = "uuid"

    def get_queryset(self) -> QuerySet[Lesson]:
        qs = lesson_queryset()
        if self.action != "list":
            return qs
        first, last = date_range(self.request)
        qs = qs.filter(date__range=(first, last))
        request = self.request
        if group := uuid_param(request, "group"):
            qs = qs.filter(course__group__pk=group)
        if teacher := uuid_param(request, "teacher"):
            qs = qs.filter(Q(teacher__pk=teacher) | Q(course__teacher__pk=teacher))
        if room := uuid_param(request, "room"):
            qs = qs.filter(room__pk=room)
        if course := uuid_param(request, "course"):
            qs = qs.filter(course__pk=course)
        if student := uuid_param(request, "student"):
            student_user = get_object_or_404(User, pk=student)
            qs = qs.filter(pk__in=Lesson.objects.for_user(student_user, "student").values("pk"))
        return qs.order_by("date", "start_time")

    @extend_schema(
        parameters=[
            *RANGE_PARAMS,
            OpenApiParameter("group", str),
            OpenApiParameter("teacher", str),
            OpenApiParameter("room", str),
            OpenApiParameter("course", str),
            OpenApiParameter("student", str),
        ]
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    def _respond(self, lesson: Lesson, warnings: Warnings, status: int = 200) -> Response:
        fresh = lesson_queryset().get(pk=lesson.pk)
        return Response(
            {"lesson": LessonSerializer(fresh).data, "warnings": warnings}, status=status
        )

    @extend_schema(request=ExtraLessonSerializer, responses={201: LessonChange})
    def create(self, request: Request) -> Response:
        """A one-off extra lesson (consultation, mock test)."""
        form = ExtraLessonSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        course = data["course"]
        teacher = data.get("teacher") or course.teacher
        room = data.get("room")
        warnings = services.check_or_raise(
            [
                services.Candidate(
                    data["date"], data["start_time"], data["end_time"], course, teacher.pk, room
                )
            ]
        )
        with transaction.atomic():
            lesson = Lesson.objects.create(
                course=course,
                date=data["date"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                room=room,
                teacher=teacher,
                lesson_type=data.get("lesson_type"),
                is_extra=True,
                planned_date=data["date"],
                planned_start_time=data["start_time"],
                planned_end_time=data["end_time"],
                planned_room=room,
            )
            audit.record(
                request=request,
                action="lesson.create_extra",
                entity=lesson,
                after=_lesson_snapshot(lesson),
            )
        return self._respond(lesson, warnings, status=201)

    @extend_schema(request=CancelSerializer, responses=LessonChange)
    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str) -> Response:
        form = CancelSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        with transaction.atomic():
            lesson = services.lock_lesson(pk, form.validated_data["version"])
            _not_editable(lesson)
            before = _lesson_snapshot(lesson)
            lesson.status = LessonStatus.CANCELLED
            lesson.cancel_reason = form.validated_data["reason"]
            lesson.version += 1
            lesson.save()
            audit.record(
                request=request,
                action="lesson.cancel",
                entity=lesson,
                before=before,
                after=_lesson_snapshot(lesson),
                reason=lesson.cancel_reason,
            )
        return self._respond(lesson, [])

    @extend_schema(request=VersionSerializer, responses=LessonChange)
    @action(detail=True, methods=["post"])
    def restore(self, request: Request, pk: str) -> Response:
        """Undo a cancellation, if the time is still free."""
        form = VersionSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        with transaction.atomic():
            lesson = services.lock_lesson(pk, form.validated_data["version"])
            if lesson.status != LessonStatus.CANCELLED:
                raise ValidationError({"detail": ["lesson_not_cancelled"]})
            warnings = services.check_or_raise([self._candidate(lesson)])
            before = _lesson_snapshot(lesson)
            lesson.status = LessonStatus.PLANNED
            lesson.cancel_reason = ""
            lesson.version += 1
            lesson.save()
            audit.record(
                request=request,
                action="lesson.restore",
                entity=lesson,
                before=before,
                after=_lesson_snapshot(lesson),
            )
        return self._respond(lesson, warnings)

    @staticmethod
    def _candidate(lesson: Lesson, **changes: Any) -> services.Candidate:
        return services.Candidate(
            changes.get("date", lesson.date),
            changes.get("start_time", lesson.start_time),
            changes.get("end_time", lesson.end_time),
            lesson.course,
            changes.get("teacher_id", lesson.teacher_id),
            changes.get("room", lesson.room),
            frozenset({lesson.pk}),
        )

    @extend_schema(request=MoveSerializer, responses=LessonChange)
    @action(detail=True, methods=["post"])
    def move(self, request: Request, pk: str) -> Response:
        """Another date, time or room. The lesson stays the same row (planned_* keep the
        template values), so «перенесено с …» can be shown."""
        form = MoveSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        with transaction.atomic():
            lesson = services.lock_lesson(pk, data["version"])
            _not_editable(lesson)
            if lesson.status == LessonStatus.CANCELLED:
                raise ValidationError({"detail": ["lesson_cancelled"]})
            warnings = services.check_or_raise(
                [
                    self._candidate(
                        lesson,
                        date=data["date"],
                        start_time=data["start_time"],
                        end_time=data["end_time"],
                        room=data["room"],
                    )
                ]
            )
            before = _lesson_snapshot(lesson)
            lesson.date = data["date"]
            lesson.start_time = data["start_time"]
            lesson.end_time = data["end_time"]
            lesson.room = data["room"]
            lesson.version += 1
            lesson.save()
            audit.record(
                request=request,
                action="lesson.move",
                entity=lesson,
                before=before,
                after=_lesson_snapshot(lesson),
            )
        return self._respond(lesson, warnings)

    @extend_schema(request=SubstituteSerializer, responses=LessonChange)
    @action(detail=True, methods=["post"])
    def substitute(self, request: Request, pk: str) -> Response:
        """A substitute teacher for this one lesson; `teacher: null` returns the course teacher."""
        form = SubstituteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        with transaction.atomic():
            lesson = services.lock_lesson(pk, form.validated_data["version"])
            _not_editable(lesson)
            teacher = form.validated_data["teacher"] or lesson.course.teacher
            warnings = services.check_or_raise([self._candidate(lesson, teacher_id=teacher.pk)])
            before = _lesson_snapshot(lesson)
            lesson.teacher = teacher
            lesson.version += 1
            lesson.save()
            audit.record(
                request=request,
                action="lesson.substitute",
                entity=lesson,
                before=before,
                after=_lesson_snapshot(lesson),
            )
        return self._respond(lesson, warnings)


# --- Teacher requests ----------------------------------------------------------------------


class AdminScheduleRequestViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,  # type: ignore[type-arg]
):
    permission_classes = (IsAdmin,)
    serializer_class = ScheduleRequestSerializer
    lookup_value_converter = "uuid"

    def get_queryset(self) -> QuerySet[ScheduleRequest]:
        qs = ScheduleRequest.objects.select_related(
            "author",
            "resolved_by",
            "proposed_room",
            "lesson__course__group",
            "lesson__course__subject",
            "lesson__course__teacher",
            "lesson__teacher",
            "lesson__room",
            "lesson__planned_room",
            "lesson__lesson_type",
        )
        if status := self.request.query_params.get("status"):
            qs = qs.filter(status=status)
        return qs

    @extend_schema(parameters=[OpenApiParameter("status", str)])
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    def _resolve(self, request: Request, pk: str, approve: bool) -> Response:
        form = ResolveSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        with transaction.atomic():
            req = ScheduleRequest.objects.select_for_update().get(pk=pk)
            if req.status != ScheduleRequest.Status.PENDING:
                raise ValidationError({"detail": ["request_not_pending"]})
            if approve:
                lesson = services.lock_lesson(
                    req.lesson_id, Lesson.objects.get(pk=req.lesson_id).version
                )
                _not_editable(lesson)
                before = _lesson_snapshot(lesson)
                if req.kind == ScheduleRequest.Kind.CANCEL:
                    lesson.status = LessonStatus.CANCELLED
                    lesson.cancel_reason = req.reason
                else:
                    room = req.proposed_room if req.proposed_room_id else lesson.room
                    services.check_or_raise(
                        [
                            AdminLessonViewSet._candidate(
                                lesson,
                                date=req.proposed_date,
                                start_time=req.proposed_start_time,
                                end_time=req.proposed_end_time,
                                room=room,
                            )
                        ]
                    )
                    lesson.date = req.proposed_date  # type: ignore[assignment]
                    lesson.start_time = req.proposed_start_time  # type: ignore[assignment]
                    lesson.end_time = req.proposed_end_time  # type: ignore[assignment]
                    lesson.room = room
                lesson.version += 1
                lesson.save()
                verb = "cancel" if req.kind == ScheduleRequest.Kind.CANCEL else "move"
                audit.record(
                    request=request,
                    action=f"lesson.{verb}",
                    entity=lesson,
                    before=before,
                    after=_lesson_snapshot(lesson),
                    reason=req.reason,
                )
            req.status = (
                ScheduleRequest.Status.APPROVED if approve else ScheduleRequest.Status.REJECTED
            )
            req.resolved_by = current_user(request)
            req.resolved_at = timezone.now()
            req.resolution_comment = form.validated_data.get("comment", "")
            req.save()
            audit.record(
                request=request,
                action=f"schedule_request.{req.status}",
                entity=req,
                after={"status": req.status, "comment": req.resolution_comment},
            )
        return Response(ScheduleRequestSerializer(self.get_queryset().get(pk=req.pk)).data)

    @extend_schema(request=ResolveSerializer, responses=ScheduleRequestSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str) -> Response:
        return self._resolve(request, pk, approve=True)

    @extend_schema(request=ResolveSerializer, responses=ScheduleRequestSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: str) -> Response:
        return self._resolve(request, pk, approve=False)


class TeacherLessonRequestView(APIView):
    """A teacher asks to cancel or move a lesson of their own."""

    permission_classes = (IsTeacher,)

    @extend_schema(request=ScheduleRequestSerializer, responses={201: ScheduleRequestSerializer})
    def post(self, request: Request, pk: str) -> Response:
        user = current_user(request)
        lesson = get_object_or_404(Lesson.objects.for_user(user, "teacher"), pk=pk)
        if lesson.status != LessonStatus.PLANNED or lesson.date < services.today():
            raise ValidationError({"detail": ["lesson_not_changeable"]})
        form = ScheduleRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        if ScheduleRequest.objects.filter(
            lesson=lesson, status=ScheduleRequest.Status.PENDING
        ).exists():
            raise ValidationError({"detail": ["request_already_pending"]})
        with transaction.atomic():
            req = form.save(lesson=lesson, author=user)
            audit.record(
                request=request,
                action="schedule_request.create",
                entity=req,
                after={"kind": req.kind, "lesson": str(lesson.pk), "reason": req.reason},
            )
        return Response(ScheduleRequestSerializer(req).data, status=201)


class TeacherRequestListView(APIView):
    permission_classes = (IsTeacher,)

    @extend_schema(responses=ScheduleRequestSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = ScheduleRequest.objects.filter(author=current_user(request)).select_related(
            "author",
            "resolved_by",
            "proposed_room",
            "lesson__course__group",
            "lesson__course__subject",
            "lesson__course__teacher",
            "lesson__teacher",
            "lesson__room",
            "lesson__planned_room",
            "lesson__lesson_type",
        )[:100]
        return Response(ScheduleRequestSerializer(qs, many=True).data)


class TeacherRequestWithdrawView(APIView):
    permission_classes = (IsTeacher,)

    @extend_schema(request=None, responses=ScheduleRequestSerializer)
    def post(self, request: Request, pk: str) -> Response:
        req = get_object_or_404(ScheduleRequest, pk=pk, author=current_user(request))
        if req.status != ScheduleRequest.Status.PENDING:
            raise ValidationError({"detail": ["request_not_pending"]})
        with transaction.atomic():
            req.status = ScheduleRequest.Status.WITHDRAWN
            req.save(update_fields=["status"])
            audit.record(request=request, action="schedule_request.withdrawn", entity=req)
        return Response(ScheduleRequestSerializer(req).data)


# --- Schedule per role ---------------------------------------------------------------------


class TeacherScheduleView(APIView):
    """«Моя неделя»: own courses, assisted courses and substitutions."""

    permission_classes = (IsTeacher,)

    @extend_schema(parameters=RANGE_PARAMS, responses=LessonSerializer(many=True))
    def get(self, request: Request) -> Response:
        first, last = date_range(request)
        scoped = Lesson.objects.for_user(current_user(request), active_role(request))
        qs = lesson_queryset(scoped).filter(date__range=(first, last))
        return Response(LessonSerializer(qs.order_by("date", "start_time"), many=True).data)


class StudentScheduleView(APIView):
    """Lessons of the groups the student belonged to on each date; cancelled ones included
    (shown struck through)."""

    permission_classes = STUDENT_PAGES

    @extend_schema(parameters=RANGE_PARAMS, responses=StudentLessonSerializer(many=True))
    def get(self, request: Request) -> Response:
        first, last = date_range(request)
        scoped = Lesson.objects.for_user(subject_student(request), "student")
        qs = lesson_queryset(scoped).filter(date__range=(first, last))
        return Response(StudentLessonSerializer(qs.order_by("date", "start_time"), many=True).data)


class RoomOptionsView(APIView):
    """Rooms for selects: administrators and teachers (move requests)."""

    permission_classes = (IsAdmin | IsTeacher,)

    @extend_schema(responses=RoomOptionSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(
            RoomOptionSerializer(Room.objects.filter(is_archived=False), many=True).data
        )


class AvailabilityView(APIView):
    """Stage 19: what the schedule forms may offer — free pairs of the group and its teacher,
    then free rooms and free teachers of the subject at the chosen time. For one date (a lesson)
    or a weekday and period (a template slot). The save still checks every conflict."""

    permission_classes = (IsAdmin,)

    @extend_schema(
        parameters=[
            OpenApiParameter("course", str, required=True),
            OpenApiParameter("date", str),
            OpenApiParameter("weekday", int),
            OpenApiParameter("valid_from", str),
            OpenApiParameter("valid_to", str),
            OpenApiParameter("start", str),
            OpenApiParameter("end", str),
            OpenApiParameter("exclude_lesson", str),
            OpenApiParameter("exclude_slot", str),
        ],
        responses=inline_serializer(
            "Availability",
            {
                "group_busy": serializers.ListField(child=serializers.DictField()),
                "free_pairs": serializers.ListField(child=serializers.DictField()),
                "rooms": serializers.ListField(child=serializers.DictField()),
                "teachers": serializers.ListField(child=serializers.DictField()),
            },
        ),
    )
    def get(self, request: Request) -> Response:
        course_id = uuid_param(request, "course")
        if course_id is None:
            raise ValidationError({"course": ["required"]})
        course = get_object_or_404(Course.objects.select_related("group", "subject"), pk=course_id)
        start, end = time_param(request, "start"), time_param(request, "end")
        if start and end and end <= start:
            raise ValidationError({"end": ["ends_before_start"]})
        day = date_param(request, "date")
        if day is not None:
            busy = services.busy_on_date(day, uuid_param(request, "exclude_lesson"))
        else:
            raw = request.query_params.get("weekday", "")
            if raw not in {"1", "2", "3", "4", "5", "6", "7"}:
                raise ValidationError({"weekday": ["invalid_choice"]})
            valid_from = date_param(request, "valid_from") or services.today()
            busy = services.busy_on_weekday(
                int(raw), valid_from, date_param(request, "valid_to"),
                uuid_param(request, "exclude_slot"),
            )  # fmt: skip
        return Response(services.availability(course, busy, start, end))
