"""Append-only audit log (SPEC §5, §10.8).

UPDATE and DELETE are rejected by a PostgreSQL trigger (migration 0002), so even a bug
in the application cannot rewrite history.
"""

from typing import ClassVar

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_constraint=True,
    )
    actor_role = models.CharField(max_length=16, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    action = models.CharField(max_length=64, db_index=True)
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering: ClassVar = ["-at", "-id"]
        indexes: ClassVar = [models.Index(fields=["entity_type", "entity_id"])]

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M} {self.action} {self.entity_type}:{self.entity_id}"
