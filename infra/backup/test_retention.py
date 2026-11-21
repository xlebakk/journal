"""uv run --project backend python -m pytest -q -p no:django infra/backup"""

from datetime import UTC, datetime, timedelta

from retention import DAILY, MONTHLY, WEEKLY, parse, to_delete


def name(when: datetime) -> str:
    return f"journal-{when:%Y%m%dT%H%M%SZ}.dump.age"


def nightly(days: int, end: datetime = datetime(2027, 6, 30, 2, 30, tzinfo=UTC)) -> list[str]:
    return [name(end - timedelta(days=i)) for i in range(days)]


def test_a_full_year_and_more_keeps_14_daily_8_weekly_12_monthly() -> None:
    names = nightly(800)
    deleted = set(to_delete(names))
    kept = [n for n in names if n not in deleted]
    dates = [parse(n) for n in kept]
    assert all(d is not None for d in dates)
    # The last 14 nights are all there.
    assert set(names[:DAILY]) <= set(kept)
    weeks = {d.isocalendar()[:2] for d in dates if d}
    months = {(d.year, d.month) for d in dates if d}
    assert len(weeks) >= WEEKLY
    assert len(months) == MONTHLY
    # Nothing older than 12 months (plus the month boundary) survives.
    oldest = min(d for d in dates if d)
    assert oldest > datetime(2026, 6, 30, tzinfo=UTC)
    assert len(kept) <= DAILY + WEEKLY + MONTHLY


def test_newest_of_a_period_is_the_one_kept() -> None:
    day = datetime(2027, 1, 10, tzinfo=UTC)
    morning, night = name(day.replace(hour=2)), name(day.replace(hour=23))
    assert to_delete([morning, night]) == [morning]


def test_few_backups_are_all_kept_and_strangers_are_ignored() -> None:
    names = nightly(5) + ["notes.txt", "journal-garbage.dump.age"]
    assert to_delete(names) == []
