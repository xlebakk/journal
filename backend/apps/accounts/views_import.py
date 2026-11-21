"""Student import and access cards (SPEC §8.2)."""

from typing import Any

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.files import read_table, xlsx_response
from apps.core.models import CenterSettings

from . import imports
from .permissions import IsAdmin
from .totp import qr_svg_data_uri

IMPORT_FORM = {
    "type": "object",
    "properties": {
        "file": {"type": "string", "format": "binary"},
        "apply": {"type": "boolean"},
    },
}


class StudentImportRowSerializer(serializers.Serializer[Any]):
    line = serializers.IntegerField()
    last_name = serializers.CharField(allow_blank=True)
    first_name = serializers.CharField(allow_blank=True)
    middle_name = serializers.CharField(allow_blank=True)
    login = serializers.CharField(allow_blank=True)
    group_name = serializers.CharField(allow_blank=True)
    issues = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField())


class CredentialSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    login = serializers.CharField()
    temporary_password = serializers.CharField()
    group_name = serializers.CharField(allow_blank=True)


class StudentImportResultSerializer(serializers.Serializer[Any]):
    applied = serializers.BooleanField()
    rows = StudentImportRowSerializer(many=True)
    created = CredentialSerializer(many=True)


class StudentImportTemplateView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(responses={(200, "application/octet-stream"): bytes})
    def get(self, request: Request) -> HttpResponse:
        return xlsx_response(
            "import-uchenikov",
            [
                ("Ученики", [imports.TEMPLATE_HEADER]),
                ("Пример", [imports.TEMPLATE_HEADER, imports.TEMPLATE_EXAMPLE]),
            ],
        )


class StudentImportView(APIView):
    """Without `apply=true` — the preview; with it — all rows in one transaction, only if
    no row has errors. Warnings (a possible duplicate) do not block the import."""

    permission_classes = (IsAdmin,)
    parser_classes = (MultiPartParser,)
    throttle_scope = "import"

    @extend_schema(
        request={"multipart/form-data": IMPORT_FORM}, responses=StudentImportResultSerializer
    )
    def post(self, request: Request) -> Response:
        form: Any = request.data
        rows = imports.parse(read_table(request.FILES.get("file")))
        apply = str(form.get("apply", "")).lower() == "true"
        created: list[dict[str, Any]] = []
        if apply and rows and not any(r.errors for r in rows):
            created = imports.apply(request, rows)
        data = {"applied": bool(created), "rows": [r.as_dict() for r in rows], "created": created}
        return Response(StudentImportResultSerializer(data).data)


class AccessCardInfoView(APIView):
    """What every access card shows besides the login and the password: the site and its QR."""

    permission_classes = (IsAdmin,)

    @extend_schema(
        responses=inline_serializer(
            "AccessCardInfo",
            fields={
                "center_name": serializers.CharField(),
                "site_url": serializers.CharField(),
                "qr": serializers.CharField(),
            },
        )
    )
    def get(self, request: Request) -> Response:
        settings = CenterSettings.load()
        return Response(
            {
                "center_name": settings.center_name,
                "site_url": settings.site_url,
                "qr": qr_svg_data_uri(settings.site_url),
            }
        )
