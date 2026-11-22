"""Announcements (SPEC §5, §8.9): for everyone, a role or groups; pinned; shown until a date.

The body is plain text; the frontend turns https:// links into links (SPEC §11).
"""

import uuid
from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.academics.models import Course, Group, GroupMembership, members_on


class Audience(models.TextChoices):
    ALL = "all", "все"
    ROLE = "role", "роль"
    GROUPS = "groups", "группы"


class AnnouncementQuerySet(models.QuerySet["Announcement"]):
    def live(self) -> "AnnouncementQuerySet":
        now = timezone.now()
        return self.filter(published_at__lte=now).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )

    def for_user(self, user: Any, role: str | None) -> "AnnouncementQuerySet":
        """What this user sees in the active role: all, their role, or their groups —
        a student's current groups, a teacher's groups of their courses."""
        if role == "admin":
            return self.all()
        groups: QuerySet[Any]
        if role == "student":
            day = timezone.localdate()
            groups = GroupMembership.objects.filter(members_on(day), student=user).values(
                "group_id"
            )
        elif role == "teacher":
            groups = Course.objects.filter(Q(teacher=user) | Q(assistants=user)).values("group_id")
        elif role == "parent":
            # A parent reads what the children read: their groups and «ученикам» (stage 14).
            day = timezone.localdate()
            groups = GroupMembership.objects.filter(
                members_on(day), student__parent_links__parent=user
            ).values("group_id")
            role = "student"
        else:
            return self.none()
        return self.filter(
            Q(audience=Audience.ALL)
            | Q(audience=Audience.ROLE, role=role)
            | Q(audience=Audience.GROUPS, groups__in=groups)
        ).distinct()


class Announcement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=5000)
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.ALL)
    role = models.CharField(max_length=16, blank=True)
    groups = models.ManyToManyField(Group, blank=True, related_name="announcements")
    pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering: ClassVar = ["-pinned", "-published_at"]
        constraints: ClassVar = [
            models.CheckConstraint(
                condition=~Q(audience=Audience.ROLE) | Q(role__in=["teacher", "student"]),
                name="announcements_role_audience",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__isnull=True) | Q(expires_at__gt=models.F("published_at")),
                name="announcements_expiry",
            ),
        ]

    def __str__(self) -> str:
        return self.title
