from __future__ import annotations

from ai_news.config import load_settings
from ai_news.jobs.check_secrets import SECRETS, _required, main, presence


def test_presence_never_prints_values() -> None:
    assert presence({"MS_CLIENT_ID": "abc"})["MS_CLIENT_ID"] is True
    assert presence({})["MS_CLIENT_ID"] is False


def test_recipients_are_not_required_while_sending_is_off() -> None:
    settings = load_settings(environ={})
    assert settings.briefing.send_enabled is False
    assert _required(settings)["BRIEFING_RECIPIENTS"] is False


def test_alert_address_is_not_required_before_alerting_exists() -> None:
    required = {secret.name for secret in SECRETS if secret.required}
    assert "ALERT_EMAIL_TO" not in required
    assert {"ANTHROPIC_API_KEY", "MS_MAILBOX", "MS_CLIENT_ID"} <= required


def test_recipients_are_required_once_sending_is_on() -> None:
    settings = load_settings(environ={})
    settings.briefing.send_enabled = True
    assert _required(settings)["BRIEFING_RECIPIENTS"] is True


def test_gate_fails_and_names_what_is_missing(monkeypatch, capsys) -> None:
    for secret in SECRETS:
        monkeypatch.delenv(secret.name, raising=False)
    code = main([])
    output = capsys.readouterr().out
    assert code == 1
    assert "Required secrets not set: ANTHROPIC_API_KEY" in output
    assert "GATE: missing required secrets" in output
    assert "BRIEFING_RECIPIENTS" not in output.split("Required secrets not set:")[1]


def test_gate_passes_when_required_secrets_are_present(monkeypatch, capsys) -> None:
    for secret in SECRETS:
        monkeypatch.setenv(secret.name, "placeholder")
    code = main([])
    output = capsys.readouterr().out
    assert code == 0
    assert "GATE: all required secrets present" in output
