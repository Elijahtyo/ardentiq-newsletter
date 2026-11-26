from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ai_news.state import RunRecord, StateError, StateStore

NOW = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)


@pytest.fixture()
def store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "pipeline_state.json", tmp_path / "runs.jsonl")


def test_first_run_uses_lookback(store: StateStore) -> None:
    assert store.window_start(NOW) == NOW - timedelta(days=3)


def test_window_starts_at_last_success(store: StateStore) -> None:
    last = NOW - timedelta(days=2)
    store.record_success(last, digest_id="d1")
    assert store.window_start(NOW) == last


def test_a_failed_run_does_not_advance_the_window(store: StateStore) -> None:
    last = NOW - timedelta(days=2)
    store.record_success(last)
    store.append(
        RunRecord(run_id="r2", started_at=NOW - timedelta(days=1), status="failed")
    )
    assert store.window_start(NOW) == last


def test_naive_timestamp_is_treated_as_utc(store: StateStore) -> None:
    store.state_file.parent.mkdir(parents=True, exist_ok=True)
    store.state_file.write_text('{"last_success_at": "2026-11-25T09:00:00"}', encoding="utf-8")
    assert store.window_start(NOW) == datetime(2026, 11, 25, 9, 0, tzinfo=UTC)


def test_future_timestamp_is_clamped_to_now(store: StateStore) -> None:
    store.record_success(NOW + timedelta(days=1))
    assert store.window_start(NOW) == NOW


def test_runs_log_round_trips(store: StateStore) -> None:
    store.append(RunRecord(run_id="r1", started_at=NOW, finished_at=NOW, status="succeeded"))
    store.append(RunRecord(run_id="r2", started_at=NOW, status="failed", errors=["feed down"]))
    runs = store.runs()
    assert [run.run_id for run in runs] == ["r1", "r2"]
    assert runs[1].errors == ["feed down"]


def test_corrupt_state_is_reported(store: StateStore) -> None:
    store.state_file.parent.mkdir(parents=True, exist_ok=True)
    store.state_file.write_text("{not json", encoding="utf-8")
    with pytest.raises(StateError):
        store.load()
