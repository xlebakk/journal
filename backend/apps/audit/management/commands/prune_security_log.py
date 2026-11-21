"""Nightly: drops refused-request records older than 30 days (the audit log is kept forever)."""

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import DeniedRequest

KEEP_DAYS = 30


class Command(BaseCommand):
    help = "Deletes DeniedRequest rows older than 30 days."

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff = timezone.now() - timedelta(days=KEEP_DAYS)
        deleted, _ = DeniedRequest.objects.filter(at__lt=cutoff).delete()
        self.stdout.write(f"deleted {deleted}")
