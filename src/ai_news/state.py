"""Run state without a database.

The brief's rule is that each run covers the window from the end of the last
*successful* run to now. With Databricks gone, that fact is kept in two files:

``state/pipeline_state.json``
    ``{"last_success_at": "2026-11-26T09:00:00+00:00", "last_digest_id": "..."}``
``state/runs.jsonl``
    one line per run: id, timings, status, counts. An audit trail, never read
    for the window calculation.

Both are committed, so the state survives the runner being thrown away between
workflow runs. A failed run never advances ``last_success_at``, so the next run
picks up the same window.
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_LOOKBACK = timedelta(days=3)


class StateError(RuntimeError):
    """Raised when the state file is present but unreadable."""


class PipelineState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_success_at: datetime | None = None
    last_digest_id: str | None = None


class RunRecord(BaseModel):
    """One pipeline run. Mirrors the old ``pipeline_runs`` row."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"
    items_fetched: int = 0
    items_kept: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    errors: list[str] = Field(default_factory=list)


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class StateStore:
    """Reads the window start and records outcomes."""

    def __init__(self, state_file: Path, runs_file: Path) -> None:
        self.state_file = Path(state_file)
        self.runs_file = Path(runs_file)

    def load(self) -> PipelineState:
        if not self.state_file.exists():
            return PipelineState()
        try:
            return PipelineState.model_validate_json(
                self.state_file.read_text(encoding="utf-8")
            )
        except ValueError as exc:
            raise StateError(f"{self.state_file} is not valid state: {exc}") from exc

    def window_start(self, now: datetime, lookback: timedelta = DEFAULT_LOOKBACK) -> datetime:
        """End of the last successful run, or a short lookback on a first run."""
        last = self.load().last_success_at
        if last is None:
            return now - lookback
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return min(last, now)

    def record_success(self, now: datetime, digest_id: str | None = None) -> PipelineState:
        state = PipelineState(last_success_at=now, last_digest_id=digest_id)
        _write_atomic(self.state_file, state.model_dump_json(indent=2) + "\n")
        return state

    def append(self, record: RunRecord) -> None:
        self.runs_file.parent.mkdir(parents=True, exist_ok=True)
        with self.runs_file.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(record.model_dump_json() + "\n")

    def runs(self) -> list[RunRecord]:
        if not self.runs_file.exists():
            return []
        return [
            RunRecord.model_validate_json(line)
            for line in self.runs_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
