"""Announcements: the administrator writes, everyone reads their own feed."""

from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import (
    IsAdmin,
    IsParent,
    IsStudent,
    IsTeacher,
    active_role,
    current_user,
)
from apps.core.viewsets import AuditedAdminViewSet

from .models import Announcement
from .serializers import AnnouncementSerializer, FeedItemSerializer


class AnnouncementAdminViewSet(AuditedAdminViewSet):
    serializer_class = AnnouncementSerializer
    audit_name = "announcement"

    def get_queryset(self) -> QuerySet[Announcement]:
        return Announcement.objects.select_related("author").prefetch_related("groups")


def feed(request: Request, *, pinned_only: bool = False, limit: int = 50) -> list[Any]:
    qs = (
        Announcement.objects.live()
        .for_user(current_user(request), active_role(request))
        .select_related("author")
    )
    if pinned_only:
        qs = qs.filter(pinned=True)
    return list(qs.order_by("-pinned", "-published_at")[:limit])


class AnnouncementFeedView(APIView):
    """Live announcements for the active role: pinned first, then the newest."""

    permission_classes = (IsAdmin | IsTeacher | IsStudent | IsParent,)

    @extend_schema(
        parameters=[OpenApiParameter("pinned", bool)], responses=FeedItemSerializer(many=True)
    )
    def get(self, request: Request) -> Response:
        pinned = request.query_params.get("pinned") == "true"
        return Response(FeedItemSerializer(feed(request, pinned_only=pinned), many=True).data)
