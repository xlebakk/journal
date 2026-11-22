"""Which backups to delete: keep 14 daily, 8 weekly and 12 monthly copies.

Reads backup file names (journal-YYYYMMDDTHHMMSSZ.dump.age) on stdin, prints the names to
delete. Kept: the newest backup of each of the last 14 days, of each of the last 8 ISO weeks
and of each of the last 12 months. Names it does not understand are never deleted.

    rclone lsf remote:journal | python3 retention.py
"""

import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime

NAME = re.compile(r"^journal-(\d{8}T\d{6}Z)\.dump\.age$")
DAILY, WEEKLY, MONTHLY = 14, 8, 12


def parse(name: str) -> datetime | None:
    match = NAME.match(name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def to_delete(names: Iterable[str]) -> list[str]:
    dated = sorted(
        ((when, name) for name in names if (when := parse(name)) is not None), reverse=True
    )
    keep: set[str] = set()
    for key, limit in (
        (lambda d: d.date(), DAILY),
        (lambda d: d.isocalendar()[:2], WEEKLY),
        (lambda d: (d.year, d.month), MONTHLY),
    ):
        periods: list[object] = []
        for when, name in dated:  # newest first: the first one seen per period is kept
            period = key(when)
            if period in periods:
                continue
            if len(periods) == limit:
                break
            periods.append(period)
            keep.add(name)
    return sorted(name for _, name in dated if name not in keep)


if __name__ == "__main__":
    for name in to_delete(line.strip() for line in sys.stdin if line.strip()):
        print(name)
