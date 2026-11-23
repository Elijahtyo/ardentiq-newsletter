"""File-backed store for LinkedIn drafts.

Replaces the old ``linkedin_drafts`` Delta table. Drafts are JSON files under
``linkedin/drafts/<digest_id>.json`` and published history is an append-only
``linkedin/published.jsonl``. Both are ordinary files, so approval is a normal
pull request or a text edit, and nothing here touches Databricks.

The store is deliberately the only component that writes draft state. Publishers
read from it; they never write back into a database.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ai_news.linkedin.models import Draft, DraftRecord, DraftStatus

# Permitted status moves. Published is terminal, and a rejected draft can be
# reopened only by generating a new one.
_TRANSITIONS: dict[DraftStatus, set[DraftStatus]] = {
    DraftStatus.DRAFT: {DraftStatus.APPROVED, DraftStatus.REJECTED},
    DraftStatus.APPROVED: {DraftStatus.PUBLISHED, DraftStatus.REJECTED},
    DraftStatus.REJECTED: set(),
    DraftStatus.PUBLISHED: set(),
}


class DraftStoreError(RuntimeError):
    """Raised for an unknown draft or an illegal status change."""


def _now() -> datetime:
    return datetime.now(UTC)


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


class DraftStore:
    """Reads and writes draft batches and the published history."""

    def __init__(self, drafts_dir: Path, published_file: Path) -> None:
        self.drafts_dir = Path(drafts_dir)
        self.published_file = Path(published_file)

    # ------------------------------------------------------------------ write

    def save_batch(
        self,
        digest_id: str,
        drafts: list[Draft],
        *,
        model: str = "",
        prompt_version: str = "",
    ) -> list[DraftRecord]:
        """Write a fresh batch. Existing records with the same id keep their status.

        Re-running the drafting job is therefore safe: a draft already approved or
        published is not reset to ``draft``.
        """
        existing = {record.draft_id: record for record in self.load(digest_id)}
        records: list[DraftRecord] = []
        for index, draft in enumerate(drafts, start=1):
            draft_id = f"{digest_id}-{index:02d}"
            if draft_id in existing:
                records.append(existing[draft_id])
                continue
            records.append(
                DraftRecord(
                    draft_id=draft_id,
                    digest_id=digest_id,
                    post_text=draft.post_text,
                    sector=draft.sector,
                    source_cluster_ids=draft.source_cluster_ids,
                    prompt_version=prompt_version,
                    model=model,
                    created_at=_now(),
                )
            )
        self._write(digest_id, records)
        return records

    def set_status(
        self,
        digest_id: str,
        draft_id: str,
        status: DraftStatus,
        *,
        edited_text: str | None = None,
        reject_reason: str | None = None,
        post_urn: str | None = None,
        impressions: int | None = None,
        reactions: int | None = None,
    ) -> DraftRecord:
        """Move one draft to a new status. Approval and rejection happen here."""
        records = self.load(digest_id)
        for index, record in enumerate(records):
            if record.draft_id != draft_id:
                continue
            if status not in _TRANSITIONS[record.status]:
                raise DraftStoreError(
                    f"{draft_id}: cannot move from {record.status} to {status}"
                )
            now = _now()
            updates: dict[str, object] = {"status": status}
            if edited_text is not None:
                updates["edited_text"] = edited_text
            if reject_reason is not None:
                updates["reject_reason"] = reject_reason
            if status is DraftStatus.APPROVED:
                updates["approved_at"] = now
            if status is DraftStatus.PUBLISHED:
                updates["published_at"] = now
                updates["post_urn"] = post_urn
            if impressions is not None:
                updates["impressions"] = impressions
            if reactions is not None:
                updates["reactions"] = reactions
            updated = record.model_copy(update=updates)
            records[index] = updated
            self._write(digest_id, records)
            if status is DraftStatus.PUBLISHED:
                self._append_published(updated)
            return updated
        raise DraftStoreError(f"no draft {draft_id!r} in {digest_id!r}")

    # ------------------------------------------------------------------- read

    def path_for(self, digest_id: str) -> Path:
        return self.drafts_dir / f"{digest_id}.json"

    def load(self, digest_id: str) -> list[DraftRecord]:
        path = self.path_for(digest_id)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [DraftRecord.model_validate(item) for item in payload.get("drafts", [])]

    def list_digests(self) -> list[str]:
        if not self.drafts_dir.exists():
            return []
        return sorted(path.stem for path in self.drafts_dir.glob("*.json"))

    def approved(self) -> list[DraftRecord]:
        """Every approved draft across batches, ready for a publisher."""
        return [
            record
            for digest_id in self.list_digests()
            for record in self.load(digest_id)
            if record.status is DraftStatus.APPROVED
        ]

    def published_history(self) -> list[dict[str, object]]:
        if not self.published_file.exists():
            return []
        return [
            json.loads(line)
            for line in self.published_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def last_published_sector(self) -> str | None:
        """Sector of the most recent post, for the no-repeat-sector rule."""
        history = self.published_history()
        return history[-1].get("sector") if history else None  # type: ignore[return-value]

    # ---------------------------------------------------------------- private

    def _write(self, digest_id: str, records: list[DraftRecord]) -> None:
        payload = {
            "digest_id": digest_id,
            "updated_at": _now().isoformat(),
            "drafts": [record.model_dump(mode="json") for record in records],
        }
        _write_atomic(
            self.path_for(digest_id),
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )

    def _append_published(self, record: DraftRecord) -> None:
        self.published_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "draft_id": record.draft_id,
            "digest_id": record.digest_id,
            "sector": str(record.sector) if record.sector else None,
            "post_urn": record.post_urn,
            "published_at": record.published_at.isoformat() if record.published_at else None,
            "post_text": record.text_to_publish,
        }
        with self.published_file.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
