"""Administrator: users CRUD and account actions (SPEC §8.2)."""

from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit

from . import credentials, lockout, sessions
from .models import Role, StudentProfile, TeacherProfile, User, UserQuerySet, UserSession
from .permissions import IsAdmin, current_user, require_recent_password
from .serializers import (
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    AdminUserWriteSerializer,
    SessionSerializer,
    StudentProfileSerializer,
    TeacherProfileSerializer,
)

USER_AUDIT_FIELDS = (
    "login",
    "last_name",
    "first_name",
    "middle_name",
    "roles",
    "is_active",
    "archived_at",
    "must_change_password",
    "totp_enabled",
)
STUDENT_AUDIT_FIELDS = tuple(StudentProfileSerializer.Meta.fields)
TEACHER_AUDIT_FIELDS = tuple(TeacherProfileSerializer.Meta.fields)

TemporaryPasswordSerializer = inline_serializer(
    "TemporaryPassword",
    fields={
        "user": AdminUserDetailSerializer(),
        "temporary_password": serializers.CharField(),
    },
)


def _user_snapshot(user: User) -> dict[str, Any]:
    data = audit.snapshot(user, USER_AUDIT_FIELDS)
    if hasattr(user, "student_profile"):
        data["student_profile"] = audit.snapshot(user.student_profile, STUDENT_AUDIT_FIELDS)
    if hasattr(user, "teacher_profile"):
        data["teacher_profile"] = audit.snapshot(user.teacher_profile, TEACHER_AUDIT_FIELDS)
    return data


def _other_active_admins(user: User) -> bool:
    return User.objects.active().with_role(Role.ADMIN).exclude(pk=user.pk).exists()


def _apply_profiles(user: User, data: dict[str, Any]) -> None:
    """Profiles exist for the matching roles; data from other roles is ignored."""
    if user.has_role(Role.STUDENT):
        profile, _ = StudentProfile.objects.get_or_create(user=user)
        for field, value in data.get("student_profile", {}).items():
            setattr(profile, field, value)
        profile.save()
    if user.has_role(Role.TEACHER):
        teacher, _ = TeacherProfile.objects.get_or_create(user=user)
        for field, value in data.get("teacher_profile", {}).items():
            setattr(teacher, field, value)
        teacher.save()


class AdminUserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,  # type: ignore[type-arg]
):
    permission_classes = (IsAdmin,)
    lookup_value_converter = "uuid"

    def get_queryset(self) -> UserQuerySet:
        qs = User.objects.for_user(current_user(self.request)).select_related(
            "student_profile", "teacher_profile"
        )
        params = self.request.query_params
        if q := params.get("q", "").strip():
            for word in q.split()[:4]:
                qs = qs.filter(
                    Q(login__icontains=word)
                    | Q(last_name__icontains=word)
                    | Q(first_name__icontains=word)
                    | Q(middle_name__icontains=word)
                )
        if (role := params.get("role")) in Role.values:
            qs = qs.with_role(role)
        match params.get("status"):
            case "active":
                qs = qs.filter(is_active=True, archived_at__isnull=True)
            case "blocked":
                qs = qs.filter(is_active=False, archived_at__isnull=True)
            case "archived":
                qs = qs.filter(archived_at__isnull=False)
        return qs

    def get_serializer_class(self) -> type[serializers.BaseSerializer[Any]]:
        if self.action == "list":
            return AdminUserListSerializer
        return AdminUserDetailSerializer

    def _detail(self, user: User) -> dict[str, Any]:
        fresh = User.objects.select_related("student_profile", "teacher_profile").get(pk=user.pk)
        return dict(AdminUserDetailSerializer(fresh).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str),
            OpenApiParameter("role", str, enum=Role.values),
            OpenApiParameter("status", str, enum=["active", "blocked", "archived"]),
        ]
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(request=AdminUserWriteSerializer, responses={201: TemporaryPasswordSerializer})
    def create(self, request: Request) -> Response:
        form = AdminUserWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        password = credentials.generate_temporary_password()
        for _attempt in range(3):
            login = data.get("login") or credentials.generate_login(
                data["last_name"], data["first_name"]
            )
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        login=login,
                        password=password,
                        last_name=data["last_name"],
                        first_name=data["first_name"],
                        middle_name=data.get("middle_name", ""),
                        roles=data["roles"],
                        must_change_password=True,
                    )
                    _apply_profiles(user, data)
                    audit.record(
                        request=request,
                        action="user.create",
                        entity=user,
                        after=_user_snapshot(user),
                    )
                break
            except IntegrityError:
                if data.get("login"):
                    return Response({"login": ["login_taken"]}, status=400)
        else:
            return Response({"login": ["login_taken"]}, status=400)
        return Response(
            {"user": self._detail(user), "temporary_password": password},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=AdminUserWriteSerializer, responses=AdminUserDetailSerializer)
    def partial_update(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        form = AdminUserWriteSerializer(instance=user, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        roles_changed = "roles" in data and sorted(data["roles"]) != sorted(user.roles)
        if roles_changed:
            require_recent_password(request)
            if Role.ADMIN in user.roles and Role.ADMIN not in data["roles"]:
                if user.pk == request.user.pk:
                    return Response({"roles": ["cannot_remove_own_admin"]}, status=400)
                if not _other_active_admins(user):
                    return Response({"roles": ["last_admin"]}, status=400)
        with transaction.atomic():
            before = _user_snapshot(user)
            for field in ("last_name", "first_name", "middle_name", "roles"):
                if field in data:
                    setattr(user, field, data[field])
            if data.get("login"):
                user.login = data["login"]
            try:
                with transaction.atomic():
                    user.save()
            except IntegrityError:
                return Response({"login": ["login_taken"]}, status=400)
            _apply_profiles(user, data)
            user = User.objects.select_related("student_profile", "teacher_profile").get(pk=user.pk)
            after = _user_snapshot(user)
            if after != before:
                audit.record(
                    request=request,
                    action="user.roles_change" if roles_changed else "user.update",
                    entity=user,
                    before=before,
                    after=after,
                )
            if roles_changed:
                sessions.end_user_sessions(user, UserSession.EndReason.ROLES_CHANGED)
        return Response(self._detail(user))

    # --- Account actions ---------------------------------------------------------------

    def _set_state(self, request: Request, user: User, action_name: str, **fields: Any) -> Response:
        with transaction.atomic():
            before = audit.snapshot(user, fields.keys())
            for field, value in fields.items():
                setattr(user, field, value)
            user.save(update_fields=list(fields))
            audit.record(
                request=request,
                action=action_name,
                entity=user,
                before=before,
                after=audit.snapshot(user, fields.keys()),
            )
            if user.is_active is False or user.archived_at is not None:
                sessions.end_user_sessions(user, UserSession.EndReason.ACCOUNT_DISABLED)
        return Response(self._detail(user))

    def _guard_self_and_last_admin(self, request: Request, user: User) -> Response | None:
        if user.pk == request.user.pk:
            return Response({"detail": "cannot_apply_to_self"}, status=400)
        if user.is_admin and not _other_active_admins(user):
            return Response({"detail": "last_admin"}, status=400)
        return None

    @extend_schema(request=None, responses=TemporaryPasswordSerializer)
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request: Request, pk: str) -> Response:
        """New temporary password; all the user's sessions end (SPEC §4)."""
        user = self.get_object()
        password = credentials.generate_temporary_password()
        with transaction.atomic():
            user.set_password(password)
            user.must_change_password = True
            user.save(update_fields=["password", "must_change_password"])
            sessions.end_user_sessions(user, UserSession.EndReason.PASSWORD_RESET)
            audit.record(request=request, action="user.password_reset", entity=user)
        lockout.clear(user.login)
        return Response({"user": self._detail(user), "temporary_password": password})

    @extend_schema(request=None, responses=AdminUserDetailSerializer)
    @action(detail=True, methods=["post"])
    def block(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        if error := self._guard_self_and_last_admin(request, user):
            return error
        return self._set_state(request, user, "user.block", is_active=False)

    @extend_schema(request=None, responses=AdminUserDetailSerializer)
    @action(detail=True, methods=["post"])
    def unblock(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        if user.is_archived:
            return Response({"detail": "user_archived"}, status=400)
        return self._set_state(request, user, "user.unblock", is_active=True)

    @extend_schema(request=None, responses=AdminUserDetailSerializer)
    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: str) -> Response:
        """Login off, sessions ended, data kept. Users are never deleted (SPEC §10.10)."""
        user = self.get_object()
        if user.is_archived:
            return Response(self._detail(user))
        if error := self._guard_self_and_last_admin(request, user):
            return error
        return self._set_state(
            request, user, "user.archive", is_active=False, archived_at=timezone.now()
        )

    @extend_schema(request=None, responses=AdminUserDetailSerializer)
    @action(detail=True, methods=["post"], url_path="unlock-login")
    def unlock_login(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        lockout.clear(user.login)
        with transaction.atomic():
            audit.record(request=request, action="user.unlock_login", entity=user)
        return Response(self._detail(user))

    @extend_schema(request=None, responses=AdminUserDetailSerializer)
    @action(detail=True, methods=["post"], url_path="reset-2fa")
    def reset_2fa(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        require_recent_password(request)
        with transaction.atomic():
            user.totp_enabled = False
            user.totp_secret = ""
            user.totp_last_counter = None
            user.save(update_fields=["totp_enabled", "totp_secret", "totp_last_counter"])
            user.backup_codes.all().delete()
            sessions.end_user_sessions(user, UserSession.EndReason.TOTP_RESET)
            audit.record(request=request, action="user.2fa_reset", entity=user)
        return Response(self._detail(user))

    @extend_schema(responses=SessionSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="sessions")
    def sessions_list(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        qs = UserSession.objects.filter(user=user, ended_at__isnull=True)
        context = {"current_session_id": sessions.current_session_id(request)}
        return Response(SessionSerializer(qs, many=True, context=context).data)

    @extend_schema(
        request=None,
        responses=inline_serializer("EndedSessions", fields={"ended": serializers.IntegerField()}),
    )
    @action(detail=True, methods=["post"], url_path="sessions/end-all")
    def sessions_end_all(self, request: Request, pk: str) -> Response:
        user = self.get_object()
        with transaction.atomic():
            ended = sessions.end_user_sessions(user, UserSession.EndReason.REVOKED)
            audit.record(
                request=request, action="user.sessions_end", entity=user, after={"ended": ended}
            )
        return Response({"ended": ended})


class AdminUserSessionView(APIView):
    """End one session of a user."""

    permission_classes = (IsAdmin,)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, pk: str, session_id: str) -> Response:
        user = get_object_or_404(User.objects.for_user(current_user(request)), pk=pk)
        record = get_object_or_404(UserSession, pk=session_id, user=user, ended_at__isnull=True)
        with transaction.atomic():
            sessions.end_session(record, UserSession.EndReason.REVOKED)
            audit.record(
                request=request,
                action="user.session_end",
                entity=user,
                after={"session_id": str(record.pk)},
            )
        return Response(status=204)
