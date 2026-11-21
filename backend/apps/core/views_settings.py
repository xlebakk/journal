"""Center settings and the logo (SPEC §2, §8.11, §11)."""

import base64
import io
import secrets
from typing import Any, ClassVar

from django.conf import settings as django_settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import GradeScale
from apps.accounts.permissions import IsAdmin, require_recent_password
from apps.audit import services as audit

from .models import CenterSettings

LOGO_SIZE = 512  # px, the longer side
LOGO_MAX_PIXELS = 40_000_000  # decompression bombs are refused before decoding
LOGO_FORMATS = ("PNG", "JPEG", "WEBP")

# field → (min, max)
RANGES: dict[str, tuple[int, int]] = {
    "lockout_threshold": (3, 20),
    "lockout_base_minutes": (1, 1440),
    "lockout_max_hours": (1, 168),
    "admin_idle_minutes": (5, 240),
    "admin_absolute_hours": (1, 24),
    "teacher_idle_minutes": (5, 720),
    "teacher_absolute_hours": (1, 72),
    "teacher_remember_days": (1, 90),
    "student_absolute_hours": (1, 72),
    "student_remember_days": (1, 90),
    "edit_window_days": (0, 60),
    "max_grades_per_lesson": (1, 9),
    "low_grade_percent": (1, 99),
    "attendance_threshold_percent": (1, 100),
    "attendance_window_days": (7, 365),
}


def logo_path(name: str) -> Any:
    return django_settings.MEDIA_ROOT / "logo" / name


def logo_data_uri(center: CenterSettings) -> str | None:
    """The logo inside the JSON, so no public file endpoint is needed."""
    if not center.logo:
        return None
    try:
        data = logo_path(center.logo).read_bytes()
    except OSError:
        return None
    return "data:image/png;base64," + base64.b64encode(data).decode()


class CenterSettingsSerializer(serializers.ModelSerializer[CenterSettings]):
    logo = serializers.SerializerMethodField()
    default_grade_scale = serializers.ChoiceField(choices=GradeScale.choices)

    class Meta:
        model = CenterSettings
        fields = (
            "center_name",
            "contacts",
            "site_url",
            *RANGES,
            "require_teacher_2fa",
            "default_grade_scale",
            "logo",
            "last_backup_at",
            "last_backup_ok",
            "updated_at",
        )
        read_only_fields = ("logo", "last_backup_at", "last_backup_ok", "updated_at")
        extra_kwargs: ClassVar = {
            name: {"min_value": low, "max_value": high} for name, (low, high) in RANGES.items()
        }

    def get_logo(self, obj: CenterSettings) -> str | None:
        return logo_data_uri(obj)

    def validate_site_url(self, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValidationError("invalid_url")
        return value.rstrip("/")


AUDIT_FIELDS = [f for f in CenterSettingsSerializer.Meta.fields if f not in ("logo", "updated_at")]


class CenterSettingsView(APIView):
    """GET for the form; PATCH changes security and journal rules, so the password must have
    been entered within the last 5 minutes."""

    permission_classes = (IsAdmin,)

    @extend_schema(responses=CenterSettingsSerializer)
    def get(self, request: Request) -> Response:
        return Response(CenterSettingsSerializer(CenterSettings.load()).data)

    @extend_schema(request=CenterSettingsSerializer, responses=CenterSettingsSerializer)
    def patch(self, request: Request) -> Response:
        require_recent_password(request)
        with transaction.atomic():
            center = CenterSettings.objects.select_for_update().get_or_create(pk=1)[0]
            before = audit.snapshot(center, AUDIT_FIELDS)
            form = CenterSettingsSerializer(center, data=request.data, partial=True)
            form.is_valid(raise_exception=True)
            form.save()
            after = audit.snapshot(center, AUDIT_FIELDS)
            changed = {k for k in after if after[k] != before[k]}
            if changed:
                audit.record(
                    request=request,
                    action="settings.update",
                    entity=center,
                    before={k: before[k] for k in changed},
                    after={k: after[k] for k in changed},
                )
        return Response(CenterSettingsSerializer(CenterSettings.load()).data)


def reencode_logo(upload: Any) -> bytes:
    """Re-encode to a fresh PNG: no metadata, no trailing data, at most 512 px."""
    if upload is None:
        raise ValidationError({"file": ["required"]})
    if upload.size > django_settings.LOGO_MAX_BYTES:
        raise ValidationError({"file": ["file_too_large"]})
    try:
        with Image.open(upload, formats=LOGO_FORMATS) as probe:
            width, height = probe.size
            if width * height > LOGO_MAX_PIXELS:
                raise ValidationError({"file": ["image_too_large"]})
            probe.load()
            image = probe.convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError({"file": ["unsupported_file"]}) from exc
    image.thumbnail((LOGO_SIZE, LOGO_SIZE))
    clean = Image.new("RGBA", image.size)
    clean.paste(image)
    out = io.BytesIO()
    clean.save(out, format="PNG", optimize=True)
    return out.getvalue()


class LogoView(APIView):
    permission_classes = (IsAdmin,)
    parser_classes = (MultiPartParser,)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        },
        responses=CenterSettingsSerializer,
    )
    def post(self, request: Request) -> Response:
        data = reencode_logo(request.FILES.get("file"))
        name = f"{secrets.token_hex(16)}.png"
        folder = logo_path("")
        folder.mkdir(parents=True, exist_ok=True)
        logo_path(name).write_bytes(data)
        self._replace(request, name)
        return Response(CenterSettingsSerializer(CenterSettings.load()).data)

    @extend_schema(responses=CenterSettingsSerializer)
    def delete(self, request: Request) -> Response:
        self._replace(request, "")
        return Response(CenterSettingsSerializer(CenterSettings.load()).data)

    def _replace(self, request: Request, name: str) -> None:
        with transaction.atomic():
            center = CenterSettings.objects.select_for_update().get_or_create(pk=1)[0]
            old = center.logo
            center.logo = name
            center.save()
            audit.record(
                request=request,
                action="settings.logo_update" if name else "settings.logo_delete",
                entity=center,
                before={"logo": bool(old)},
                after={"logo": bool(name)},
            )
            if old:
                transaction.on_commit(lambda: logo_path(old).unlink(missing_ok=True))
