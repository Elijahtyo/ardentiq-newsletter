from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai_news.config import ScheduleSettings
from ai_news.jobs.guard import should_run

S = ScheduleSettings()


@pytest.mark.parametrize(
    ("utc", "expected"),
    [
        # Winter (GMT = UTC): 09:00 UTC run fires, 08:00 UTC does not.
        (datetime(2026, 11, 23, 9, 0, tzinfo=UTC), True),   # Mon
        (datetime(2026, 11, 23, 8, 0, tzinfo=UTC), False),
        (datetime(2026, 11, 26, 9, 12, tzinfo=UTC), True),  # Thu, started late
        # Summer (BST = UTC+1): 08:00 UTC run fires, 09:00 UTC does not.
        (datetime(2026, 6, 15, 8, 0, tzinfo=UTC), True),    # Mon
        (datetime(2026, 6, 15, 9, 0, tzinfo=UTC), False),
        # Not a run day.
        (datetime(2026, 11, 24, 9, 0, tzinfo=UTC), False),  # Tue
        # Day the clocks go back (Sun 25 Oct 2026) then the next Monday.
        (datetime(2026, 10, 26, 9, 0, tzinfo=UTC), True),
        (datetime(2026, 10, 26, 8, 0, tzinfo=UTC), False),
        # First Thursday of BST (clocks go forward Sun 29 Mar 2026).
        (datetime(2026, 4, 2, 8, 0, tzinfo=UTC), True),
        (datetime(2026, 4, 2, 9, 0, tzinfo=UTC), False),
    ],
)
def test_exactly_one_trigger_runs(utc: datetime, expected: bool) -> None:
    assert should_run(utc, S)[0] is expected


def test_naive_time_rejected() -> None:
    with pytest.raises(ValueError):
        should_run(datetime(2026, 11, 23, 9, 0), S)  # noqa: DTZ001
