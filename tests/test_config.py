from __future__ import annotations

from pathlib import Path

import pytest

from ai_news.config import ConfigError, expand_env, load_settings, repo_root
from ai_news.sources import load_sources, summarise


def test_expand_env_default_and_missing() -> None:
    assert expand_env("${A:-x}", {}) == "x"
    assert expand_env({"k": ["${A}"]}, {"A": "1"}) == {"k": ["1"]}
    with pytest.raises(ConfigError):
        expand_env("${MISSING}", {})


def test_settings_load_with_defaults() -> None:
    settings = load_settings(environ={})
    assert settings.models.filtering == "claude-haiku-5-5"
    assert settings.models.drafting == "claude-sonnet-5-5"
    assert settings.linkedin.publishing_enabled is False
    assert settings.briefing.send_enabled is False
    assert settings.state.state_file == "state/pipeline_state.json"


def test_settings_need_no_service_credentials_to_load() -> None:
    """Secrets arrive at run time; nothing in the config file is required to parse it."""
    settings = load_settings(environ={})
    assert settings.briefing.recipients_env == "BRIEFING_RECIPIENTS"


def test_committed_sources_file_is_valid() -> None:
    parsed = load_sources(repo_root() / "config" / "sources.yaml")
    stats = summarise(parsed)
    assert stats["active"] >= 20, "Phase 0 gate needs at least 20 verified sources"


def test_no_secret_values_in_config() -> None:
    for path in (repo_root() / "config").glob("*.yaml"):
        text = Path(path).read_text(encoding="utf-8").lower()
        for marker in ("sk-ant-", "client_secret:", "bearer ", "access_token:"):
            assert marker not in text, f"{path.name} looks like it holds a secret"


def test_databricks_is_gone() -> None:
    """The warehouse was removed deliberately; nothing may reintroduce it."""
    settings = load_settings(environ={})
    assert not hasattr(settings, "databricks")
    text = (repo_root() / "config" / "settings.yaml").read_text(encoding="utf-8").lower()
    assert "databricks" not in text
