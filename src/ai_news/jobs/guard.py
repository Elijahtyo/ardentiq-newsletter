"""Schedule guard for the digest workflow.

GitHub cron is UTC only, so digest.yml fires at both 08:00 and 09:00 UTC on
Mondays and Thursdays. Exactly one of those is 09:xx in London (BST or GMT).
This step lets that one through and stops the other.

It always exits 0. It writes ``run=true|false`` to $GITHUB_OUTPUT, and later
steps run only when run == 'true'.

    python -m ai_news.jobs.guard            # decide from the current time
    python -m ai_news.jobs.guard --force    # always run (manual dispatch)
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from ai_news.config import ScheduleSettings, load_settings

_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def should_run(now_utc: datetime, schedule: ScheduleSettings) -> tuple[bool, str]:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    local = now_utc.astimezone(ZoneInfo(schedule.timezone))
    day = _DAYS[local.weekday()]
    if day not in schedule.run_days:
        return False, f"{local:%a %H:%M %Z} is not a run day"
    start = local.replace(
        hour=schedule.target_hour, minute=schedule.target_minute, second=0, microsecond=0
    )
    minutes_late = (local - start).total_seconds() / 60
    if 0 <= minutes_late < schedule.guard_window_minutes:
        return True, f"{local:%a %H:%M %Z} is inside the run window"
    return False, f"{local:%a %H:%M %Z} is outside the run window"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="decide and print only")
    args = parser.parse_args(argv)

    if args.force:
        run, reason = True, "forced by manual dispatch"
    else:
        run, reason = should_run(datetime.now(UTC), load_settings_schedule())
    print(f"guard: run={str(run).lower()} ({reason})")
    output = os.environ.get("GITHUB_OUTPUT")
    if output and not args.dry_run:
        with open(output, "a", encoding="utf-8") as handle:  # noqa: PTH123
            handle.write(f"run={str(run).lower()}\n")
    return 0


def load_settings_schedule() -> ScheduleSettings:
    """The guard must not need secrets, so fall back to defaults if settings won't expand."""
    try:
        return load_settings().schedule
    except Exception:  # noqa: BLE001
        return ScheduleSettings()


if __name__ == "__main__":
    raise SystemExit(main())
