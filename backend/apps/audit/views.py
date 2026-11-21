"""Read-only audit and login history for administrators. The screens come in stage 5."""

from datetime import date
from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import LoginEvent
from apps.accounts.permissions import IsAdmin
from apps.accounts.serializers import LoginEventSerializer

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer[AuditLog]):
    actor_id = serializers.UUIDField(read_only=True, allow_null=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "at",
            "actor_id",
            "actor_name",
            "actor_role",
            "ip",
            "action",
            "entity_type",
            "entity_id",
            "before",
            "after",
            "reason",
        )
        read_only_fields = fields

    def get_actor_name(self, entry: AuditLog) -> str | None:
        return entry.actor.full_name if entry.actor else None


def _date_param(request: Request, name: str) -> date | None:
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({name: ["invalid_date"]}) from exc


DATE_PARAMS = [OpenApiParameter("date_from", str), OpenApiParameter("date_to", str)]


class AuditLogListView(generics.ListAPIView[AuditLog]):
    permission_classes = (IsAdmin,)
    serializer_class = AuditLogSerializer

    def get_queryset(self) -> QuerySet[AuditLog]:
        qs = AuditLog.objects.select_related("actor")
        params = self.request.query_params
        for name in ("action", "entity_type", "entity_id"):
            if value := params.get(name):
                qs = qs.filter(**{name: value})
        if actor := params.get("actor"):
            qs = qs.filter(actor__pk=actor)
        if since := _date_param(self.request, "date_from"):
            qs = qs.filter(at__date__gte=since)
        if until := _date_param(self.request, "date_to"):
            qs = qs.filter(at__date__lte=until)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter("action", str),
            OpenApiParameter("entity_type", str),
            OpenApiParameter("entity_id", str),
            OpenApiParameter("actor", str),
            *DATE_PARAMS,
        ]
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)


class LoginEventListView(generics.ListAPIView[LoginEvent]):
    permission_classes = (IsAdmin,)
    serializer_class = LoginEventSerializer

    def get_queryset(self) -> QuerySet[LoginEvent]:
        qs = LoginEvent.objects.all()
        params = self.request.query_params
        if login := params.get("login"):
            qs = qs.filter(login_attempted__icontains=login.strip().lower())
        if (success := params.get("success")) in ("true", "false"):
            qs = qs.filter(success=success == "true")
        if since := _date_param(self.request, "date_from"):
            qs = qs.filter(at__date__gte=since)
        if until := _date_param(self.request, "date_to"):
            qs = qs.filter(at__date__lte=until)
        return qs

    @extend_schema(
        parameters=[OpenApiParameter("login", str), OpenApiParameter("success", bool), *DATE_PARAMS]
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)
