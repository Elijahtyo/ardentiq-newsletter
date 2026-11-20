"""Load and validate the source registry."""

from __future__ import annotations

from pathlib import Path

import yaml

from ai_news.config import ConfigError, repo_root
from ai_news.models import Source, SourcesFile


def sources_path(path: Path | None = None) -> Path:
    return path or (repo_root() / "config" / "sources.yaml")


def load_sources(path: Path | None = None) -> SourcesFile:
    target = sources_path(path)
    if not target.is_file():
        raise ConfigError(f"sources file not found: {target}")
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{target}: top-level YAML must be a mapping")
    parsed = SourcesFile.model_validate(raw)
    _check_duplicate_urls(parsed)
    return parsed


def _check_duplicate_urls(parsed: SourcesFile) -> None:
    """Two active feeds pointing at the same URL would double-count every story."""
    seen: dict[str, str] = {}
    clashes: list[str] = []
    for source in parsed.active():
        if not source.url:
            continue
        normalised = source.url.rstrip("/").lower()
        if normalised in seen:
            clashes.append(f"{seen[normalised]} and {source.source_id} -> {source.url}")
        else:
            seen[normalised] = source.source_id
    if clashes:
        raise ConfigError("duplicate active source urls: " + "; ".join(clashes))


def summarise(parsed: SourcesFile) -> dict[str, int]:
    active = parsed.active()
    by_tier: dict[str, int] = {}
    for source in active:
        key = f"tier{source.tier}"
        by_tier[key] = by_tier.get(key, 0) + 1
    by_tier["total"] = len(parsed.sources)
    by_tier["active"] = len(active)
    by_tier["uk"] = sum(1 for source in active if source.region == "uk")
    return by_tier


def eligible(source: Source) -> bool:
    return source.active and source.type != "email"
