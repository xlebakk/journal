"""Nightly job (cron): lessons four weeks ahead from the week template. Idempotent."""

from typing import Any

from django.core.management.base import BaseCommand

from apps.schedule import services


class Command(BaseCommand):
    help = "Generates lessons from the week template for the next four weeks."

    def handle(self, *args: Any, **options: Any) -> None:
        created = services.generate_lessons()
        first, last = services.horizon()
        self.stdout.write(f"Lessons created: {created} ({first.isoformat()} — {last.isoformat()})")
