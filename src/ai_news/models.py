"""Pydantic models shared across the pipeline.

These are the contracts between pipeline stages and the shapes every LLM call
must validate against. Nothing here talks to the network.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Sector(StrEnum):
    """The six focus sectors. Slugs are stable; labels are for display."""

    FINANCIAL_SERVICES = "financial_services"
    BUSINESS_SERVICES = "business_services"
    HEALTHCARE_SERVICES = "healthcare_services"
    TECH_ENABLED_SERVICES = "tech_enabled_services"
    LOGISTICS_AND_DISTRIBUTION = "logistics_and_distribution"
    PROFESSIONAL_SERVICES = "professional_services"


SECTOR_LABELS: dict[Sector, str] = {
    Sector.FINANCIAL_SERVICES: "Financial services",
    Sector.BUSINESS_SERVICES: "Business services",
    Sector.HEALTHCARE_SERVICES: "Healthcare services",
    Sector.TECH_ENABLED_SERVICES: "Tech-enabled services",
    Sector.LOGISTICS_AND_DISTRIBUTION: "Logistics and distribution",
    Sector.PROFESSIONAL_SERVICES: "Professional services",
}


class ContentPolicy(StrEnum):
    """How much of a source we are allowed to store.

    ``HEADLINE_ONLY`` covers Reuters and the FT: we keep the headline, link and
    timestamp, never article text.
    """

    FULL = "full"
    EXCERPT_ONLY = "excerpt_only"
    HEADLINE_ONLY = "headline_only"


class Source(BaseModel):
    """One entry in ``config/sources.yaml``."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    type: Literal["rss", "email", "api"]
    url: str | None = None
    region: Literal["uk", "global"] | None = None
    tier: Literal[1, 2, 3]
    uk_priority: int = Field(default=0, ge=0, le=3)
    sectors: list[Sector] = Field(default_factory=list)
    active: bool = True
    content_policy: ContentPolicy = ContentPolicy.FULL
    notes: str | None = Field(
        default=None,
        description="Human note. YAML-only; not written to the Delta table.",
    )

    @model_validator(mode="after")
    def _check_url(self) -> Source:
        if self.type in {"rss", "api"} and not self.url:
            raise ValueError(f"{self.source_id}: {self.type} source needs a url")
        if self.type == "email" and self.url:
            raise ValueError(f"{self.source_id}: email sources take a mailbox, not a url")
        return self

    def table_row(self) -> dict[str, object]:
        """Columns exactly as defined for the ``sources`` Delta table."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "type": self.type,
            "url": self.url,
            "region": self.region,
            "tier": self.tier,
            "uk_priority": self.uk_priority,
            "sectors": [str(sector) for sector in self.sectors],
            "active": self.active,
        }


class SourcesFile(BaseModel):
    """The whole ``config/sources.yaml`` document."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    updated: date | None = None
    sources: list[Source]

    @field_validator("sources")
    @classmethod
    def _unique_ids(cls, sources: list[Source]) -> list[Source]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for source in sources:
            if source.source_id in seen:
                duplicates.add(source.source_id)
            seen.add(source.source_id)
        if duplicates:
            raise ValueError(f"duplicate source_id(s): {sorted(duplicates)}")
        return sources

    def active(self) -> list[Source]:
        return [source for source in self.sources if source.active]


class Claim(BaseModel):
    """A single factual assertion carried in a summary."""

    model_config = ConfigDict(extra="forbid")

    text: str
    single_source: bool = Field(
        default=False, description="True when only one outlet is reporting this."
    )
    primary_source: bool = Field(
        default=False,
        description="True when the claim comes from the originating body "
        "(regulator, company, paper).",
    )


class Tags(BaseModel):
    """Filter-and-tag model output for one cluster."""

    model_config = ConfigDict(extra="forbid")

    is_ai: bool
    topics: list[str] = Field(default_factory=list)
    sectors: list[Sector] = Field(default_factory=list)
    uk_relevance: int = Field(ge=0, le=5)
    sme_relevance: int = Field(ge=0, le=5)
    importance: int = Field(ge=0, le=5)

    @field_validator("sectors")
    @classmethod
    def _cap_sectors(cls, sectors: list[Sector]) -> list[Sector]:
        deduped = list(dict.fromkeys(sectors))
        if len(deduped) > 2:
            raise ValueError("at most two sectors per item")
        return deduped


class Summary(BaseModel):
    """Summarise model output for one cluster."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="Two sentences, drawn only from the fetched text.")
    why_it_matters: str = Field(description="One line on why this matters to UK SMEs.")
    claims: list[Claim] = Field(default_factory=list)


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


class RawItem(BaseModel):
    """One fetched item, before dedupe/enrichment."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    source_id: str
    url: str
    title: str
    published_at: datetime | None
    fetched_at: datetime
    excerpt: str | None = None
    content_hash: str
