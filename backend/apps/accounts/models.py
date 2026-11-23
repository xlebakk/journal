"""Users, profiles, sessions and login history."""

import uuid
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class Role(models.TextChoices):
    ADMIN = "admin", "администратор"
    TEACHER = "teacher", "преподаватель"
    STUDENT = "student", "ученик"
    # Reserved for later: linked to children through ParentLink, no UI yet.
    PARENT = "parent", "родитель"


# Seniority: the senior role opens after login and defines session strictness.
ROLE_SENIORITY: tuple[str, ...] = (Role.ADMIN, Role.TEACHER, Role.PARENT, Role.STUDENT)


class AdminSection(models.TextChoices):
    """What a super administrator can grant to another administrator (stage 16)."""

    USERS = "users", "пользователи, импорт, родители"
    STRUCTURE = "structure", "группы и справочники"
    SCHEDULE = "schedule", "расписание и запросы"
    JOURNAL = "journal", "журнал"
    EXAMS = "exams", "пробные тесты"
    REPORTS = "reports", "отчёты"
    PAYMENTS = "payments", "оплаты"
    ANNOUNCEMENTS = "announcements", "объявления"
    AUDIT = "audit", "аудит"
    SETTINGS = "settings", "настройки центра"


def senior_role(roles: list[str]) -> str:
    return min(roles, key=ROLE_SENIORITY.index)


class UserQuerySet(models.QuerySet["User"]):
    def for_user(self, user: "User") -> "UserQuerySet":
        """Users the given user may see. Everything else must look like 404."""
        if user.is_admin:
            return self.all()
        # Teachers see their students from stage 2 (courses); until then — only themselves.
        return self.filter(pk=user.pk)

    def active(self) -> "UserQuerySet":
        return self.filter(is_active=True, archived_at__isnull=True)

    def with_role(self, role: str) -> "UserQuerySet":
        return self.filter(roles__contains=[role])


class UserManager(BaseUserManager["User"]):
    def get_queryset(self) -> UserQuerySet:
        return UserQuerySet(self.model, using=self._db)

    def for_user(self, user: "User") -> UserQuerySet:
        return self.get_queryset().for_user(user)

    def active(self) -> UserQuerySet:
        return self.get_queryset().active()

    def with_role(self, role: str) -> UserQuerySet:
        return self.get_queryset().with_role(role)

    def get_by_natural_key(self, username: str | None) -> "User":
        return self.get(login=normalize_login(username or ""))

    def create_user(self, login: str, password: str | None = None, **fields: Any) -> "User":
        user = self.model(login=normalize_login(login), **fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


def normalize_login(value: str) -> str:
    """Logins are case-insensitive and trimmed."""
    return value.strip().lower()


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    login = models.CharField(max_length=64, unique=True)
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    roles = ArrayField(models.CharField(max_length=16, choices=Role.choices), default=list)
    is_active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    # TOTP secret encrypted with TOTP_ENCRYPTION_KEYS (apps.accounts.totp).
    totp_secret = models.TextField(blank=True)
    totp_enabled = models.BooleanField(default=False)
    # Last accepted TOTP time step: a code cannot be used twice.
    totp_last_counter = models.BigIntegerField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Stage 16: a super administrator has every section and manages other administrators;
    # an ordinary administrator has only the sections granted here.
    is_superadmin = models.BooleanField(default=False)
    admin_sections = ArrayField(
        models.CharField(max_length=16, choices=AdminSection.choices), default=list, blank=True
    )
    # Stage 19: the staff member's title the super administrator gives («Завуч», «Бухгалтер»).
    position = models.CharField(max_length=80, blank=True)

    USERNAME_FIELD = "login"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["last_name", "first_name"]

    objects = UserManager()

    class Meta:
        ordering: ClassVar = ["last_name", "first_name", "login"]
        constraints: ClassVar = [
            models.UniqueConstraint(Lower("login"), name="accounts_user_login_ci_unique"),
            models.CheckConstraint(
                condition=Q(login=Lower("login")), name="accounts_user_login_lowercase"
            ),
            models.CheckConstraint(condition=Q(roles__len__gte=1), name="accounts_user_has_role"),
            models.CheckConstraint(
                condition=Q(roles__contained_by=[r.value for r in Role]),
                name="accounts_user_known_roles",
            ),
            models.CheckConstraint(
                condition=Q(admin_sections__contained_by=[s.value for s in AdminSection]),
                name="accounts_user_known_admin_sections",
            ),
            # A student account never combines with another role.
            models.CheckConstraint(
                condition=~Q(roles__contains=[Role.STUDENT], roles__len__gt=1),
                name="accounts_user_student_exclusive",
            ),
        ]
        indexes: ClassVar = [models.Index(fields=["last_name", "first_name"])]

    def __str__(self) -> str:
        return self.login

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.last_name, self.first_name, self.middle_name) if p)

    @property
    def short_name(self) -> str:
        """«Алиев Ф.» — journal rows."""
        return f"{self.last_name} {self.first_name[:1]}."

    @property
    def initials(self) -> str:
        """First letter of the first name + of the last name: Фарход Алиев → «ФА»."""
        return (self.first_name[:1] + self.last_name[:1]).upper()

    def has_role(self, role: str) -> bool:
        return role in self.roles

    @property
    def is_admin(self) -> bool:
        return Role.ADMIN in self.roles

    def may_open(self, section: str) -> bool:
        """An administration section, for this administrator."""
        return self.is_admin and (self.is_superadmin or section in self.admin_sections)

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    @property
    def can_log_in(self) -> bool:
        return self.is_active and not self.is_archived

    @property
    def senior_role(self) -> str:
        return senior_role(self.roles)


class StudentProfile(models.Model):
    class SchoolGrade(models.IntegerChoices):
        GRADE_9 = 9, "9"
        GRADE_10 = 10, "10"
        GRADE_11 = 11, "11"

    user = models.OneToOneField(
        User, on_delete=models.PROTECT, primary_key=True, related_name="student_profile"
    )
    phone = models.CharField(max_length=32, blank=True)
    school = models.CharField(max_length=200, blank=True)
    school_grade = models.PositiveSmallIntegerField(choices=SchoolGrade.choices, null=True)
    target = models.CharField(max_length=200, blank=True)
    target_score = models.PositiveSmallIntegerField(null=True, blank=True)
    # Visible to administrators only.
    parent_name = models.CharField(max_length=200, blank=True)
    parent_phone = models.CharField(max_length=32, blank=True)
    admin_note = models.TextField(blank=True)

    class Meta:
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=Q(school_grade__isnull=True) | Q(school_grade__in=[9, 10, 11]),
                name="accounts_student_school_grade_range",
            ),
        ]

    def __str__(self) -> str:
        return f"student:{self.user_id}"


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.PROTECT, primary_key=True, related_name="teacher_profile"
    )
    phone = models.CharField(max_length=32, blank=True)
    subjects = models.ManyToManyField("academics.Subject", blank=True, related_name="teachers")

    def __str__(self) -> str:
        return f"teacher:{self.user_id}"


class ParentLink(models.Model):
    """Parent ↔ child. Reserved for the future parent role."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(User, on_delete=models.PROTECT, related_name="children_links")
    student = models.ForeignKey(User, on_delete=models.PROTECT, related_name="parent_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["parent", "student"], name="accounts_parent_link_unique"
            ),
            models.CheckConstraint(
                condition=~Q(parent=models.F("student")), name="accounts_parent_link_not_self"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.parent_id} → {self.student_id}"


class BackupCode(models.Model):
    """One-time 2FA recovery code, stored as a keyed hash."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="backup_codes")
    code_hash = models.CharField(max_length=128)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(
                fields=["user", "code_hash"], name="accounts_backup_code_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"backup-code:{self.user_id}"


class UserSession(models.Model):
    """Server-side record of a login, for the «Активные сеансы» list and revocation.

    A web login is a Django session (cookie); an app login (Android, stage 6) is a chain of
    refresh tokens. Both are ended the same way, so revocation covers phones too.
    """

    class Kind(models.TextChoices):
        WEB = "web"
        APP = "app"

    class EndReason(models.TextChoices):
        LOGOUT = "logout"
        REVOKED = "revoked"
        IDLE = "idle_timeout"
        EXPIRED = "absolute_timeout"
        PASSWORD_CHANGED = "password_changed"
        PASSWORD_RESET = "password_reset"
        ACCOUNT_DISABLED = "account_disabled"
        ROLES_CHANGED = "roles_changed"
        TOTP_RESET = "totp_reset"
        TOKEN_REUSE = "token_reuse"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    kind = models.CharField(max_length=3, choices=Kind.choices, default=Kind.WEB)
    key_hash = models.CharField(max_length=64, db_index=True, blank=True)
    # App sessions keep the active role here; web sessions keep it in the Django session.
    active_role = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    remember = models.BooleanField(default=False)
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=32, choices=EndReason.choices, blank=True)

    class Meta:
        ordering: ClassVar = ["-last_seen_at"]
        indexes: ClassVar = [
            models.Index(
                fields=["user"], condition=Q(ended_at__isnull=True), name="accounts_session_active"
            )
        ]

    def __str__(self) -> str:
        return f"session:{self.pk}"

    @property
    def is_active(self) -> bool:
        return self.ended_at is None


class RefreshToken(models.Model):
    """One link of an app session's chain. Only the hash is stored.

    Each refresh marks the token used and issues the next one; presenting a used token again
    means it was copied, so the whole session ends (`token_reuse`).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE, related_name="tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"refresh:{self.pk}"


class LoginEvent(models.Model):
    class Reason(models.TextChoices):
        OK = "ok"
        INVALID_CREDENTIALS = "invalid_credentials"
        LOCKED = "locked"
        IP_LIMIT = "ip_limit"
        TOTP_REQUIRED = "totp_required"
        TOTP_INVALID = "totp_invalid"
        TOTP_LIMIT = "totp_limit"
        BACKUP_CODE = "backup_code"

    at = models.DateTimeField(auto_now_add=True, db_index=True)
    # The attempted login as typed (normalised); never the password.
    login_attempted = models.CharField(max_length=64)
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="login_events"
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    success = models.BooleanField()
    reason = models.CharField(max_length=32, choices=Reason.choices)

    class Meta:
        ordering: ClassVar = ["-at"]

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M} {self.login_attempted} {self.reason}"
