"""Personal iCal link: issue, reissue, revoke; the feed itself is public."""

from datetime import timedelta
from typing import Any

from django.db import transaction
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsStudent, IsTeacher, active_role, current_user
from apps.audit import services as audit
from apps.core.models import CenterSettings

from . import calendar
from .models import CalendarFeed


class MyCalendarSerializer(serializers.Serializer[Any]):
    url = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    last_used_at = serializers.DateTimeField(allow_null=True)


def _link(request: Request, feed: CalendarFeed) -> str:
    path = reverse("calendar-feed", kwargs={"pk": feed.pk})
    return request.build_absolute_uri(f"{path}?token={calendar.token_for(feed.pk)}")


def _mine(request: Request) -> CalendarFeed | None:
    mine = CalendarFeed.objects.filter(user=current_user(request), role=active_role(request))
    return mine.first()


def _payload(request: Request, feed: CalendarFeed | None) -> dict[str, Any]:
    return {
        "url": _link(request, feed) if feed else None,
        "created_at": feed.created_at if feed else None,
        "last_used_at": feed.last_used_at if feed else None,
    }


class MyCalendarView(APIView):
    """The link for the active role: a teacher's lessons or a student's groups."""

    permission_classes = (IsTeacher | IsStudent,)

    @extend_schema(responses=MyCalendarSerializer)
    def get(self, request: Request) -> Response:
        return Response(MyCalendarSerializer(_payload(request, _mine(request))).data)

    @extend_schema(request=None, responses={201: MyCalendarSerializer})
    def post(self, request: Request) -> Response:
        """Issue a link, or reissue it: the old one stops working at once."""
        with transaction.atomic():
            old = _mine(request)
            old_id = str(old.pk) if old else None  # delete() clears the pk
            if old is not None:
                old.delete()
            feed = CalendarFeed.objects.create(
                user=current_user(request), role=active_role(request) or ""
            )
            audit.record(
                request=request,
                action="calendar.reissue" if old else "calendar.issue",
                entity=feed,
                before={"id": old_id} if old_id else None,
                after={"id": str(feed.pk), "role": feed.role},
            )
        return Response(MyCalendarSerializer(_payload(request, feed)).data, status=201)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request: Request) -> Response:
        with transaction.atomic():
            feed = _mine(request)
            if feed is not None:
                audit.record(
                    request=request,
                    action="calendar.revoke",
                    entity=feed,
                    before={"id": str(feed.pk), "role": feed.role},
                )
                feed.delete()
        return Response(status=204)


class CalendarFeedThrottle(SimpleRateThrottle):
    """Per link, not per IP: Google and Apple fetch everyone's calendars from shared servers."""

    scope = "calendar"

    def get_cache_key(self, request: Request, view: Any) -> str:
        return self.cache_format % {"scope": self.scope, "ident": view.kwargs.get("pk")}


class CalendarFeedView(APIView):
    """`GET /calendar/<id>.ics?token=…` — public, because calendar apps cannot log in.

    The token is in the query string: gunicorn logs only the path and Caddy masks `token`, so
    it stays out of the access logs. Wrong id or token, a blocked owner
    or a removed role — 404.
    """

    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (CalendarFeedThrottle,)

    @extend_schema(
        parameters=[OpenApiParameter("token", str, required=True)],
        responses={(200, "text/calendar"): OpenApiResponse(OpenApiTypes.STR)},
    )
    def get(self, request: Request, pk: str) -> HttpResponse:
        feed = CalendarFeed.objects.select_related("user").filter(pk=pk).first()
        token = request.query_params.get("token", "")
        if feed is None or not calendar.check_token(feed.pk, token) or not calendar.is_live(feed):
            raise Http404
        now = timezone.now()
        if feed.last_used_at is None or now - feed.last_used_at > timedelta(hours=1):
            CalendarFeed.objects.filter(pk=feed.pk).update(last_used_at=now)
        body = calendar.render(feed, CenterSettings.load().center_name)
        response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = 'inline; filename="schedule.ics"'
        return response
