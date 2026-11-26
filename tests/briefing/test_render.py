"""Tests for rendering. Fixtures live here rather than in conftest so each file reads alone."""

from __future__ import annotations

from datetime import UTC, datetime

from ai_news.briefing.models import Briefing, BriefingItem, BriefingSection
from ai_news.briefing.render import render_html, render_text, subject_for


def _briefing(**overrides: object) -> Briefing:
    base = {
        "digest_id": "d1",
        "headline": "AI news for small firms",
        "window_start": datetime(2026, 11, 23, 9, 0, tzinfo=UTC),
        "window_end": datetime(2026, 11, 26, 9, 0, tzinfo=UTC),
        "intro": "Three things worth ten minutes.",
        "sections": [
            BriefingSection(
                heading="UK",
                items=[
                    BriefingItem(
                        cluster_id="c1",
                        title="Regulator issues guidance",
                        summary="The regulator published guidance.",
                        why_it_matters="Check your AI use against it this quarter.",
                        urls=["https://example.com/a"],
                    )
                ],
            )
        ],
        "watch": ["15 Dec: consultation closes"],
    }
    base.update(overrides)
    return Briefing(**base)  # type: ignore[arg-type]


def test_text_contains_the_briefing_content() -> None:
    text = render_text(_briefing())
    assert "AI news for small firms" in text
    assert "UK" in text
    assert "1. Regulator issues guidance" in text
    assert "Why it matters: Check your AI use against it this quarter." in text
    assert "https://example.com/a" in text
    assert "WATCH LIST" in text
    assert "15 Dec: consultation closes" in text


def test_html_is_self_contained() -> None:
    html = render_html(_briefing())
    assert html.startswith("<!doctype html>")
    assert "<style" not in html, "styles must be inline for Outlook"
    assert 'lang="en-GB"' in html


def test_html_escapes_untrusted_text() -> None:
    """Fetched text is untrusted, so it must never reach the email as markup."""
    briefing = _briefing(
        headline='<script>alert("x")</script>',
        sections=[
            BriefingSection(
                heading="<b>UK</b>",
                items=[
                    BriefingItem(
                        cluster_id="c1",
                        title="<img src=x onerror=alert(1)>",
                        summary="Mouse & keyboard",
                        why_it_matters="Quotes ' matter too",
                    )
                ],
            )
        ],
        watch=["<a href='x'>click</a>"],
    )
    html = render_html(briefing)
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html
    assert "Mouse &amp; keyboard" in html
    assert "&#x27;" in html or "&quot;" in html


def test_urls_must_be_http() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BriefingItem(
            cluster_id="c1",
            title="t",
            summary="s",
            why_it_matters="w",
            urls=["javascript:alert(1)"],
        )


def test_subject_includes_date_and_headline() -> None:
    assert subject_for(_briefing(), "AI briefing") == (
        "AI briefing — 26 November 2026: AI news for small firms"
    )


def test_item_count() -> None:
    assert _briefing().item_count == 1


def test_empty_sections_are_skipped() -> None:
    briefing = _briefing()
    briefing.sections.append(BriefingSection(heading="SME angle", items=[]))
    assert "SME ANGLE" not in render_text(briefing)
    assert "SME angle" not in render_html(briefing)
