"""Center settings: a single row, changed by administrators without code (SPEC §2).

Fields are added stage by stage; changes are written to the audit log.
"""

from typing import Any, ClassVar

from django.core.cache import cache
from django.db import models
from django.db.models import Q


class CenterSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    center_name = models.CharField(max_length=200, default="Учебный центр")
    contacts = models.CharField(max_length=300, blank=True)
    site_url = models.CharField(max_length=200, default="https://journal.example.com")

    # Login lockout: N failures → base minutes, doubling on repeat, up to max hours.
    lockout_threshold = models.PositiveSmallIntegerField(default=5)
    lockout_base_minutes = models.PositiveSmallIntegerField(default=15)
    lockout_max_hours = models.PositiveSmallIntegerField(default=24)

    # Sessions (SPEC §2).
    admin_idle_minutes = models.PositiveSmallIntegerField(default=30)
    admin_absolute_hours = models.PositiveSmallIntegerField(default=8)
    teacher_idle_minutes = models.PositiveSmallIntegerField(default=120)
    teacher_absolute_hours = models.PositiveSmallIntegerField(default=12)
    teacher_remember_days = models.PositiveSmallIntegerField(default=14)
    student_absolute_hours = models.PositiveSmallIntegerField(default=12)
    student_remember_days = models.PositiveSmallIntegerField(default=30)

    # 2FA is always required for administrators; for teachers — by this switch.
    require_teacher_2fa = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints: ClassVar = [
            models.CheckConstraint(condition=Q(id=1), name="core_settings_singleton"),
        ]

    def __str__(self) -> str:
        return self.center_name

    CACHE_KEY: ClassVar[str] = "core:center-settings"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @classmethod
    def load(cls) -> "CenterSettings":
        """Read on every request (session timeouts), so cached for a minute."""
        obj: CenterSettings | None = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 60)
        return obj
