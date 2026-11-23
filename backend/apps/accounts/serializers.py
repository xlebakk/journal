"""Explicit field lists only (no __all__); admin and self-service serializers are separate."""

from typing import Any, ClassVar

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from apps.academics.serializers import current_groups_of

from . import credentials, lockout
from .middleware import totp_setup_required
from .models import (
    AdminSection,
    LoginEvent,
    Role,
    StudentProfile,
    TeacherProfile,
    User,
    UserSession,
    normalize_login,
)
from .permissions import active_role

# Roles an administrator can assign. «parent» since stage 14; a student has no other role.
ASSIGNABLE_ROLES = (Role.ADMIN, Role.TEACHER, Role.PARENT, Role.STUDENT)


def validate_roles(roles: list[str]) -> list[str]:
    unique = list(dict.fromkeys(roles))
    if not unique:
        raise serializers.ValidationError("roles_required")
    if any(r not in ASSIGNABLE_ROLES for r in unique):
        raise serializers.ValidationError("unknown_role")
    if Role.STUDENT in unique and len(unique) > 1:
        raise serializers.ValidationError("student_role_exclusive")
    return unique


# --- Self-service ----------------------------------------------------------------------


class LoginSerializer(serializers.Serializer[Any]):
    login = serializers.CharField(max_length=64, trim_whitespace=True)
    password = serializers.CharField(max_length=256, trim_whitespace=False)
    remember = serializers.BooleanField(default=False)


class TotpCodeSerializer(serializers.Serializer[Any]):
    code = serializers.CharField(max_length=16)


class PasswordChangeSerializer(serializers.Serializer[Any]):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False)
    new_password = serializers.CharField(max_length=256, trim_whitespace=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        user: User = self.context["request"].user
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError({"new_password": ["same_as_current"]})
        if problems := password_problems(attrs["new_password"], user):
            raise serializers.ValidationError({"new_password": problems})
        return attrs


def password_problems(password: str, user: User | None = None) -> list[str]:
    """Machine codes of the password rules: password_too_short, password_too_common,
    password_too_similar (translated in the frontend)."""
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        return [str(e.code) for e in exc.error_list]
    return []


class AdminPasswordSerializer(serializers.Serializer[Any]):
    """The administrator types the password (stage 16); nothing is generated."""

    password = serializers.CharField(
        max_length=256, trim_whitespace=False, write_only=True, allow_blank=True
    )
    must_change_password = serializers.BooleanField(required=False, default=False)

    def validate_password(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("required")
        return value


class PasswordSerializer(serializers.Serializer[Any]):
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class RoleSwitchSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(choices=Role.choices)


class MeSerializer(serializers.ModelSerializer[User]):
    full_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)
    active_role = serializers.SerializerMethodField()
    totp_setup_required = serializers.SerializerMethodField()
    groups = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "login",
            "last_name",
            "first_name",
            "middle_name",
            "full_name",
            "initials",
            "roles",
            "active_role",
            "must_change_password",
            "totp_enabled",
            "totp_setup_required",
            "is_superadmin",
            "admin_sections",
            "position",
            "groups",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=Role.choices, allow_null=True))
    def get_active_role(self, user: User) -> str | None:
        return active_role(self.context["request"])

    @extend_schema_field(
        inline_serializer(
            "MeGroup",
            fields={"id": serializers.UUIDField(), "name": serializers.CharField()},
            many=True,
        )
    )
    def get_groups(self, user: User) -> list[dict[str, str]]:
        """Current groups — shown to students in the initials menu."""
        if active_role(self.context["request"]) != Role.STUDENT:
            return []
        return current_groups_of(user)

    def get_totp_setup_required(self, user: User) -> bool:
        return totp_setup_required(user)


class SessionSerializer(serializers.ModelSerializer[UserSession]):
    current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = (
            "id",
            "kind",
            "created_at",
            "last_seen_at",
            "ip",
            "user_agent",
            "remember",
            "current",
        )
        read_only_fields = fields

    def get_current(self, session: UserSession) -> bool:
        return str(session.pk) == self.context.get("current_session_id")


class BrandingSerializer(serializers.Serializer[Any]):
    center_name = serializers.CharField()
    contacts = serializers.CharField()
    logo = serializers.CharField(allow_null=True)
    brand_color = serializers.CharField()
    login_video = serializers.CharField(allow_null=True)


# --- Administrator ---------------------------------------------------------------------


class StudentProfileSerializer(serializers.ModelSerializer[StudentProfile]):
    class Meta:
        model = StudentProfile
        fields = (
            "phone",
            "school",
            "school_grade",
            "target",
            "target_score",
            "parent_name",
            "parent_phone",
            "admin_note",
        )
        extra_kwargs: ClassVar = {"school_grade": {"required": False}}


class TeacherProfileSerializer(serializers.ModelSerializer[TeacherProfile]):
    class Meta:
        model = TeacherProfile
        fields = ("phone", "subjects")
        extra_kwargs: ClassVar = {"subjects": {"required": False}}


def user_status(user: User) -> str:
    if user.is_archived:
        return "archived"
    return "active" if user.is_active else "blocked"


class AdminUserListSerializer(serializers.ModelSerializer[User]):
    full_name = serializers.CharField(read_only=True)
    status = serializers.SerializerMethodField()
    # Stage 19: what a teacher teaches, right in the list.
    subjects = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "login",
            "last_name",
            "first_name",
            "middle_name",
            "full_name",
            "roles",
            "status",
            "totp_enabled",
            "last_login",
            "created_at",
            "is_superadmin",
            "admin_sections",
            "position",
            "subjects",
        )
        read_only_fields = fields

    def get_status(self, user: User) -> str:
        return user_status(user)

    def get_subjects(self, user: User) -> list[str]:
        profile = getattr(user, "teacher_profile", None)
        if profile is None or Role.TEACHER not in user.roles:
            return []
        return [subject.name for subject in profile.subjects.all()]


class AdminUserDetailSerializer(AdminUserListSerializer):
    student_profile = StudentProfileSerializer(read_only=True, allow_null=True)
    teacher_profile = TeacherProfileSerializer(read_only=True, allow_null=True)
    login_locked_minutes = serializers.SerializerMethodField()

    class Meta(AdminUserListSerializer.Meta):
        fields: tuple[str, ...] = (  # type: ignore[assignment]
            *AdminUserListSerializer.Meta.fields,
            "must_change_password",
            "password_changed_at",
            "archived_at",
            "student_profile",
            "teacher_profile",
            "login_locked_minutes",
        )
        read_only_fields = fields  # type: ignore[assignment]

    def get_login_locked_minutes(self, user: User) -> int:
        seconds = lockout.locked_seconds(user.login)
        return lockout.minutes(seconds) if seconds else 0

    def to_representation(self, instance: User) -> dict[str, Any]:
        data = super().to_representation(instance)
        if not hasattr(instance, "student_profile"):
            data["student_profile"] = None
        if not hasattr(instance, "teacher_profile"):
            data["teacher_profile"] = None
        return data


class AdminUserWriteSerializer(serializers.Serializer[Any]):
    """Create and update. Profiles are created when the matching role is present."""

    last_name = serializers.CharField(max_length=100)
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    login = serializers.CharField(max_length=64, required=False, allow_blank=True)
    roles = serializers.ListField(child=serializers.CharField(max_length=16))
    student_profile = StudentProfileSerializer(required=False)
    teacher_profile = TeacherProfileSerializer(required=False)
    # Create only: the administrator sets the first password (stage 16).
    password = serializers.CharField(
        max_length=256, trim_whitespace=False, write_only=True, required=False, allow_blank=True
    )
    must_change_password = serializers.BooleanField(required=False, default=False)
    # Stage 16: written only by the super administrator.
    is_superadmin = serializers.BooleanField(required=False)
    admin_sections = serializers.ListField(
        child=serializers.ChoiceField(choices=AdminSection.choices), required=False
    )
    position = serializers.CharField(max_length=80, required=False, allow_blank=True)

    def validate_roles(self, roles: list[str]) -> list[str]:
        return validate_roles(roles)

    def validate_login(self, value: str) -> str:
        if not value:
            return value
        login = normalize_login(value)
        if not credentials.is_valid_login(login):
            raise serializers.ValidationError("invalid_login")
        qs = User.objects.filter(login=login)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("login_taken")
        return login

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        for field in ("last_name", "first_name", "middle_name"):
            if field in attrs:
                attrs[field] = " ".join(attrs[field].split())
        return attrs


class LoginEventSerializer(serializers.ModelSerializer[LoginEvent]):
    user_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = LoginEvent
        fields = ("id", "at", "login_attempted", "user_id", "ip", "user_agent", "success", "reason")
        read_only_fields = fields
