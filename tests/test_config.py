from __future__ import annotations

from pathlib import Path

import pytest

from ai_news.config import ConfigError, expand_env, load_settings, repo_root
from ai_news.sources import load_sources, summarise

ENV = {
    "DATABRICKS_HOST": "https://dbc-test.cloud.databricks.com",
    "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc",
}


def test_expand_env_default_and_missing() -> None:
    assert expand_env("${A:-x}", {}) == "x"
    assert expand_env({"k": ["${A}"]}, {"A": "1"}) == {"k": ["1"]}
    with pytest.raises(ConfigError):
        expand_env("${MISSING}", {})


def test_settings_load_with_defaults() -> None:
    settings = load_settings(environ=ENV)
    assert settings.databricks.qualified_schema == "main.ai_news"
    assert settings.models.filtering == "claude-haiku-5-5"
    assert settings.models.drafting == "claude-sonnet-5-5"
    assert settings.linkedin.publishing_enabled is False


def test_settings_need_databricks_host() -> None:
    with pytest.raises(ConfigError):
        load_settings(environ={})


def test_committed_sources_file_is_valid() -> None:
    parsed = load_sources(repo_root() / "config" / "sources.yaml")
    stats = summarise(parsed)
    assert stats["active"] >= 20, "Phase 0 gate needs at least 20 verified sources"


def test_no_secret_values_in_config() -> None:
    for path in (repo_root() / "config").glob("*.yaml"):
        text = Path(path).read_text(encoding="utf-8").lower()
        for marker in ("sk-ant-", "dapi", "client_secret:"):
            assert marker not in text, f"{path.name} looks like it holds a secret"
