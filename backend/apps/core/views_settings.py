"""Center settings, the logo, the brand colour and the login video."""

import base64
import io
import re
import secrets
from typing import Any, ClassVar

from django.conf import settings as django_settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from drf_spectacular.utils import extend_schema
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
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


def video_path(name: str) -> Any:
    return django_settings.MEDIA_ROOT / "video" / name


VIDEO_TYPES = {"mp4": "video/mp4", "webm": "video/webm"}
VIDEO_NAME = re.compile(r"^[0-9a-f]{32}\.(mp4|webm)$")


def login_video_url(center: CenterSettings) -> str | None:
    """The file name changes with every upload, so the address can be cached for good."""
    return f"/api/v1/branding/video/{center.login_video}" if center.login_video else None


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
    login_video = serializers.SerializerMethodField()
    default_grade_scale = serializers.ChoiceField(choices=GradeScale.choices)

    class Meta:
        model = CenterSettings
        fields = (
            "center_name",
            "contacts",
            "site_url",
            *RANGES,
            "require_admin_2fa",
            "require_teacher_2fa",
            "default_grade_scale",
            "brand_color",
            "logo",
            "login_video",
            "last_backup_at",
            "last_backup_ok",
            "last_restore_check_at",
            "last_restore_check_ok",
            "updated_at",
        )
        read_only_fields = (
            "logo",
            "login_video",
            "last_backup_at",
            "last_backup_ok",
            "last_restore_check_at",
            "last_restore_check_ok",
            "updated_at",
        )
        extra_kwargs: ClassVar = {
            name: {"min_value": low, "max_value": high} for name, (low, high) in RANGES.items()
        }

    def get_logo(self, obj: CenterSettings) -> str | None:
        return logo_data_uri(obj)

    def get_login_video(self, obj: CenterSettings) -> str | None:
        return login_video_url(obj)

    def validate_brand_color(self, value: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValidationError("invalid_color")
        return value.lower()

    def validate_site_url(self, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValidationError("invalid_url")
        return value.rstrip("/")


NOT_AUDITED = ("logo", "login_video", "updated_at")
AUDIT_FIELDS = [f for f in CenterSettingsSerializer.Meta.fields if f not in NOT_AUDITED]


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


def check_video(upload: Any) -> str:
    """MP4 or WebM by its first bytes, not by the name; returns the extension."""
    if upload is None:
        raise ValidationError({"file": ["required"]})
    if upload.size > django_settings.LOGIN_VIDEO_MAX_BYTES:
        raise ValidationError({"file": ["file_too_large"]})
    head = upload.read(16)
    upload.seek(0)
    if head[4:8] == b"ftyp":
        return "mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    raise ValidationError({"file": ["unsupported_video"]})


class LoginVideoView(APIView):
    """The video of the login page (stage 19): uploaded in the settings, played muted in a loop."""

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
        upload: UploadedFile[Any] | None = request.FILES.get("file")
        extension = check_video(upload)
        if upload is None:  # pragma: no cover — check_video refused it
            raise ValidationError({"file": ["required"]})
        name = f"{secrets.token_hex(16)}.{extension}"
        video_path("").mkdir(parents=True, exist_ok=True)
        with video_path(name).open("wb") as out:
            for chunk in upload.chunks():
                out.write(chunk)
        self._replace(request, name)
        return Response(CenterSettingsSerializer(CenterSettings.load()).data)

    @extend_schema(responses=CenterSettingsSerializer)
    def delete(self, request: Request) -> Response:
        self._replace(request, "")
        return Response(CenterSettingsSerializer(CenterSettings.load()).data)

    def _replace(self, request: Request, name: str) -> None:
        with transaction.atomic():
            center = CenterSettings.objects.select_for_update().get_or_create(pk=1)[0]
            old = center.login_video
            center.login_video = name
            center.save()
            audit.record(
                request=request,
                action="settings.video_update" if name else "settings.video_delete",
                entity=center,
                before={"login_video": bool(old)},
                after={"login_video": bool(name)},
            )
            if old:
                transaction.on_commit(lambda: video_path(old).unlink(missing_ok=True))


RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def cached[R: HttpResponse | FileResponse](response: R) -> R:
    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


class LoginVideoFileView(APIView):
    """Public: the login page plays it before anyone signs in. Only the current file is served;
    the name is random, so it is cached for good. Byte ranges for Safari's player."""

    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()

    @extend_schema(exclude=True)
    def get(self, request: Request, name: str) -> HttpResponse | FileResponse:
        if not VIDEO_NAME.match(name) or name != CenterSettings.load().login_video:
            raise Http404
        path = video_path(name)
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise Http404 from exc
        content_type = VIDEO_TYPES[name.rsplit(".", 1)[1]]
        wanted = RANGE.match(request.headers.get("Range", ""))
        if wanted and (wanted[1] or wanted[2]):
            if wanted[1]:
                start = int(wanted[1])
                end = min(int(wanted[2]) if wanted[2] else size - 1, size - 1)
            else:
                start, end = max(0, size - int(wanted[2])), size - 1
            if start > end or start >= size:
                response = HttpResponse(status=416)
                response["Content-Range"] = f"bytes */{size}"
                return response
            with path.open("rb") as source:
                source.seek(start)
                body = source.read(end - start + 1)
            partial = HttpResponse(body, status=206, content_type=content_type)
            partial["Content-Range"] = f"bytes {start}-{end}/{size}"
            return cached(partial)
        return cached(FileResponse(path.open("rb"), content_type=content_type))
