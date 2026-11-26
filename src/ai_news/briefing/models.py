"""Briefing content models.

These are what the digest stage hands to the sender. Nothing here performs I/O,
so the content can be rendered to a file, an email or a test fixture unchanged.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BriefingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_id: str
    title: str
    summary: str = Field(description="Two sentences, drawn only from the fetched text.")
    why_it_matters: str = Field(description="One line for a UK SME audience.")
    urls: list[str] = Field(default_factory=list, description="Sources the summary is grounded in")

    @field_validator("urls")
    @classmethod
    def _http_only(cls, urls: list[str]) -> list[str]:
        for url in urls:
            if not url.startswith(("https://", "http://")):
                raise ValueError(f"only http(s) links are allowed: {url!r}")
        return urls


class BriefingSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    items: list[BriefingItem] = Field(default_factory=list)


class Briefing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    digest_id: str
    headline: str
    window_start: datetime
    window_end: datetime
    intro: str = Field(default="", description="Two or three sentences setting up the issue.")
    sections: list[BriefingSection] = Field(default_factory=list)
    watch: list[str] = Field(
        default_factory=list, description="Upcoming dates and decisions worth watching."
    )

    @property
    def item_count(self) -> int:
        return sum(len(section.items) for section in self.sections)
