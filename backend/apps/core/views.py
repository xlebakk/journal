import logging

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """Liveness and dependency check. Public: reveals only ok / unavailable."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        responses=inline_serializer("Health", fields={"status": serializers.CharField()})
    )
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            cache.set("health:ping", "1", timeout=5)
        except Exception:
            logger.exception("Health check failed")
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})


def not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse({"detail": "not_found"}, status=404)


def server_error(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"detail": "server_error"}, status=500)
