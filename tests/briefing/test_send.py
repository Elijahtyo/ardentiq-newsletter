from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_news.briefing.models import Briefing
from ai_news.briefing.send import (
    FileSender,
    SendError,
    build_sendmail_payload,
    parse_recipients,
)

BRIEFING = Briefing(
    digest_id="d1",
    headline="AI news for small firms",
    window_start=datetime(2026, 11, 23, 9, 0, tzinfo=UTC),
    window_end=datetime(2026, 11, 26, 9, 0, tzinfo=UTC),
    intro="Three things worth ten minutes.",
)


def test_recipients_accept_commas_semicolons_newlines() -> None:
    raw = "a@example.com, b@example.com;c@example.com\nd@example.com"
    assert parse_recipients(raw) == [
        "a@example.com",
        "b@example.com",
        "c@example.com",
        "d@example.com",
    ]


def test_recipients_deduplicate_case_insensitively() -> None:
    assert parse_recipients("A@Example.com, a@example.com") == ["A@Example.com"]


def test_recipients_ignore_blank_chunks() -> None:
    assert parse_recipients(" , a@example.com , ") == ["a@example.com"]


@pytest.mark.parametrize("raw", ["", "   ", "not-an-email", "a@example.com, oops"])
def test_invalid_lists_raise(raw: str) -> None:
    with pytest.raises(SendError):
        parse_recipients(raw)


def test_payload_puts_every_recipient_in_bcc() -> None:
    """BCC keeps client addresses private from each other."""
    payload = build_sendmail_payload(
        sender="news@example.com",
        recipients=["a@example.com", "b@example.com"],
        subject="Subject",
        html="<p>hi</p>",
        text="hi",
    )
    message = payload["message"]
    assert message["toRecipients"] == []
    assert [r["emailAddress"]["address"] for r in message["bccRecipients"]] == [
        "a@example.com",
        "b@example.com",
    ]
    assert message["body"] == {"contentType": "HTML", "content": "<p>hi</p>"}
    assert payload["saveToSentItems"] is True


def test_payload_refuses_no_recipients() -> None:
    with pytest.raises(SendError):
        build_sendmail_payload(
            sender="news@example.com", recipients=[], subject="s", html="h", text="t"
        )


def test_file_sender_writes_both_formats(tmp_path: Path) -> None:
    sender = FileSender(tmp_path, "AI briefing", footer="Unsubscribe by reply.")
    message = sender.send(BRIEFING, ["a@example.com"])

    html = (tmp_path / "d1.html").read_text(encoding="utf-8")
    text = (tmp_path / "d1.txt").read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert "Unsubscribe by reply." in html
    assert "Unsubscribe by reply." in text
    assert "dry run" in message
    assert "1 recipient" in message


def test_file_sender_refuses_no_recipients(tmp_path: Path) -> None:
    with pytest.raises(SendError):
        FileSender(tmp_path, "AI briefing").send(BRIEFING, [])
    assert not (tmp_path / "d1.html").exists()
