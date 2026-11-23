from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_news.linkedin import Draft, DraftStatus, DraftStore
from ai_news.linkedin.store import DraftStoreError
from ai_news.models import Sector


def _draft(sector: Sector | None = Sector.FINANCIAL_SERVICES) -> Draft:
    return Draft(
        hook="A regulator published new guidance.",
        body="Here is what changes for a 20-person firm.",
        hashtags=["AI", "compliance"],
        sector=sector,
        source_cluster_ids=["c1"],
        self_check="Grounded in the source pack.",
    )


@pytest.fixture()
def store(tmp_path: Path) -> DraftStore:
    return DraftStore(tmp_path / "drafts", tmp_path / "published.jsonl")


def test_save_and_load_round_trip(store: DraftStore) -> None:
    records = store.save_batch(
        "d1",
        [_draft(), _draft(Sector.HEALTHCARE_SERVICES)],
        model="m",
        prompt_version="v1",
    )
    assert [r.draft_id for r in records] == ["d1-01", "d1-02"]
    assert all(r.status is DraftStatus.DRAFT for r in records)
    assert store.load("d1") == records
    assert store.list_digests() == ["d1"]


def test_approval_is_the_gate(store: DraftStore) -> None:
    store.save_batch("d1", [_draft()])
    assert store.approved() == []
    record = store.set_status("d1", "d1-01", DraftStatus.APPROVED)
    assert record.approved_at is not None
    assert [r.draft_id for r in store.approved()] == ["d1-01"]


def test_illegal_transitions_are_refused(store: DraftStore) -> None:
    store.save_batch("d1", [_draft()])
    with pytest.raises(DraftStoreError):
        store.set_status("d1", "d1-01", DraftStatus.PUBLISHED)
    store.set_status("d1", "d1-01", DraftStatus.REJECTED)
    with pytest.raises(DraftStoreError):
        store.set_status("d1", "d1-01", DraftStatus.APPROVED)


def test_unknown_draft_raises(store: DraftStore) -> None:
    with pytest.raises(DraftStoreError):
        store.set_status("missing", "nope", DraftStatus.APPROVED)


def test_rerun_does_not_reset_approved_or_duplicate(store: DraftStore) -> None:
    store.save_batch("d1", [_draft()])
    store.set_status("d1", "d1-01", DraftStatus.APPROVED)
    store.save_batch("d1", [_draft()])
    assert [r.status for r in store.load("d1")] == [DraftStatus.APPROVED]


def test_edited_text_wins_when_publishing(store: DraftStore) -> None:
    store.save_batch("d1", [_draft()])
    store.set_status("d1", "d1-01", DraftStatus.APPROVED, edited_text="Edited by a human.")
    record = store.set_status("d1", "d1-01", DraftStatus.PUBLISHED, post_urn="urn:li:share:1")
    assert record.text_to_publish == "Edited by a human."
    assert record.published_at is not None


def test_published_history_and_sector_rotation(store: DraftStore) -> None:
    store.save_batch("d1", [_draft()])
    store.set_status("d1", "d1-01", DraftStatus.APPROVED)
    store.set_status("d1", "d1-01", DraftStatus.PUBLISHED, post_urn="urn:li:share:1")

    history = store.published_history()
    assert len(history) == 1
    assert history[0]["post_urn"] == "urn:li:share:1"
    assert store.last_published_sector() == "financial_services"


def test_files_are_human_editable_json(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts", tmp_path / "published.jsonl")
    store.save_batch("d1", [_draft()])
    payload = json.loads((tmp_path / "drafts" / "d1.json").read_text(encoding="utf-8"))
    assert payload["digest_id"] == "d1"
    assert payload["drafts"][0]["status"] == "draft"


def test_linkedin_package_does_not_import_databricks() -> None:
    package = Path(__file__).resolve().parents[2] / "src" / "ai_news" / "linkedin"
    banned = ("ai_news.storage", "databricks")
    for source in package.glob("*.py"):
        for line in source.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                assert not any(term in stripped for term in banned), f"{source.name}: {stripped}"
