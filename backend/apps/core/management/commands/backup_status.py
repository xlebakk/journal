"""Called by the backup scripts on the server (infra/backup): what the settings page shows.

manage.py backup_status --backup ok|failed
manage.py backup_status --restore-check ok|failed
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.models import CenterSettings


class Command(BaseCommand):
    help = "Records the result of the nightly backup or of the monthly restore check."

    def add_arguments(self, parser: Any) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--backup", choices=["ok", "failed"])
        group.add_argument("--restore-check", choices=["ok", "failed"])

    def handle(
        self, *args: Any, backup: str | None, restore_check: str | None, **options: Any
    ) -> None:
        center = CenterSettings.load()
        now = timezone.now()
        if backup is not None:
            center.last_backup_at = now
            center.last_backup_ok = backup == "ok"
        elif restore_check is not None:
            center.last_restore_check_at = now
            center.last_restore_check_ok = restore_check == "ok"
        else:  # pragma: no cover - argparse requires one of them
            raise CommandError("--backup or --restore-check")
        center.save()
        self.stdout.write(f"recorded at {now:%Y-%m-%d %H:%M}")
