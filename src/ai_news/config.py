"""Configuration loading.

Non-secret configuration lives in ``config/settings.yaml``. Secrets never appear
in that file; they arrive as environment variables (GitHub Actions secrets) and
are referenced with ``${VAR}`` or ``${VAR:-default}`` placeholders.

Loading a settings file with a missing variable raises immediately, so a
misconfigured workflow fails in the first step rather than halfway through a run.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


class ConfigError(RuntimeError):
    """Raised when configuration is missing or malformed."""


def expand_env(value: Any, environ: dict[str, str] | None = None) -> Any:
    """Recursively substitute ``${VAR}`` and ``${VAR:-default}`` in a config tree."""
    env = os.environ if environ is None else environ

    if isinstance(value, str):
        def _replace(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            if name in env and env[name] != "":
                return env[name]
            if default is not None:
                return default
            raise ConfigError(f"required environment variable {name!r} is not set")

        return _ENV_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {key: expand_env(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_env(item, env) for item in value]
    return value


def repo_root() -> Path:
    """Locate the repository root (the directory holding ``config/``)."""
    override = os.environ.get("AI_NEWS_HOME")
    if override:
        return Path(override).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "config" / "settings.yaml").is_file():
            return parent
    return Path.cwd()


class DatabricksSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = Field(description="Workspace URL, e.g. https://dbc-xxxx.cloud.databricks.com")
    http_path: str = Field(description="SQL warehouse HTTP path, e.g. /sql/1.0/warehouses/abc123")
    catalog: str = "main"
    schema_name: str = Field(default="ai_news", alias="schema")
    token_env: str = "DATABRICKS_TOKEN"

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @property
    def qualified_schema(self) -> str:
        return f"{self.catalog}.{self.schema_name}"


class ModelSettings(BaseModel):
    """Model choice per pipeline stage. Nothing model-related is hard-coded."""

    model_config = ConfigDict(extra="forbid")

    filtering: str
    summarising: str
    digest: str
    drafting: str
    rubric: str


class ScheduleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str = "Europe/London"
    target_hour: int = Field(default=9, ge=0, le=23)
    target_minute: int = Field(default=0, ge=0, le=59)
    guard_window_minutes: int = Field(default=60, ge=1, le=180)
    run_days: list[str] = Field(default_factory=lambda: ["mon", "thu"])


class PipelineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    digest_min_items: int = Field(default=10, ge=1)
    digest_max_items: int = Field(default=12, ge=1)
    near_duplicate_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    max_sectors_per_item: int = Field(default=2, ge=0, le=3)

    def model_post_init(self, _ctx: Any) -> None:
        if self.digest_max_items < self.digest_min_items:
            raise ValueError("digest_max_items must be >= digest_min_items")


class LinkedInSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publishing_enabled: bool = False
    organisation_urn: str = ""
    api_version: str = "202411"
    drafts_per_digest: int = Field(default=3, ge=1, le=5)
    hashtags_max: int = Field(default=3, ge=0, le=5)


class HttpSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0, le=10)
    user_agent: str = "ai-news-pipeline/0.1"


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    databricks: DatabricksSettings
    models: ModelSettings
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    linkedin: LinkedInSettings = Field(default_factory=LinkedInSettings)
    http: HttpSettings = Field(default_factory=HttpSettings)
    sources_file: str = "config/sources.yaml"


def settings_path(path: Path | None = None) -> Path:
    return path or (repo_root() / "config" / "settings.yaml")


def load_settings(
    path: Path | None = None, *, environ: dict[str, str] | None = None
) -> Settings:
    """Read, expand and validate ``settings.yaml``."""
    target = settings_path(path)
    if not target.is_file():
        raise ConfigError(f"settings file not found: {target}")
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{target}: top-level YAML must be a mapping")
    return Settings.model_validate(expand_env(raw, environ))
