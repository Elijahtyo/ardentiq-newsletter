"""Models for the LinkedIn branch.

``Draft`` is the shape the drafting model must return. ``DraftRecord`` is the
stored form: the generated text, the human edit, the approval state and the
publishing outcome. Neither is a Databricks row; both are serialised to JSON in
the repository.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_news.models import Sector


class DraftStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class Draft(BaseModel):
    """LinkedIn draft model output."""

    model_config = ConfigDict(extra="forbid")

    hook: str
    body: str
    hashtags: list[str] = Field(default_factory=list)
    sector: Sector | None = None
    source_cluster_ids: list[str]
    self_check: str

    @field_validator("hashtags")
    @classmethod
    def _hashtags(cls, tags: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in tags:
            tag = raw.strip().lstrip("#")
            if tag and not any(ch.isspace() for ch in tag):
                cleaned.append(tag)
            elif tag:
                raise ValueError(f"hashtag may not contain spaces: {tag!r}")
        if len(cleaned) > 3:
            raise ValueError("at most 3 hashtags")
        return cleaned

    @property
    def post_text(self) -> str:
        tag_line = " ".join(f"#{tag}" for tag in self.hashtags)
        return "\n\n".join(part for part in (self.hook, self.body, tag_line) if part)


class DraftRecord(BaseModel):
    """One stored draft, including approval and publishing state."""

    model_config = ConfigDict(extra="forbid")

    draft_id: str
    digest_id: str
    status: DraftStatus = DraftStatus.DRAFT
    post_text: str = Field(description="Text as generated")
    edited_text: str | None = Field(
        default=None, description="Text after human edits; feeds the voice tuning loop"
    )
    reject_reason: str | None = None
    sector: Sector | None = None
    source_cluster_ids: list[str] = Field(default_factory=list)
    prompt_version: str = ""
    model: str = ""
    impressions: int | None = None
    reactions: int | None = None
    created_at: datetime
    approved_at: datetime | None = None
    published_at: datetime | None = None
    post_urn: str | None = None

    @property
    def text_to_publish(self) -> str:
        """The edited text when a human changed it, otherwise the generated text."""
        return self.edited_text or self.post_text
