from __future__ import annotations

from pathlib import Path

import httpx

from ai_news.jobs.audit_sources import (
    CandidateResult,
    FeedCheck,
    _parse_feed,
    build_sources_document,
)
from ai_news.models import SourcesFile

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _response(body: bytes, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=body, headers={"content-type": "application/rss+xml"})


def test_parses_recorded_rss() -> None:
    check = _parse_feed("https://x/feed", _response((FIXTURES / "sample_rss.xml").read_bytes()))
    assert check.ok and check.entries == 2
    check.robots_allowed = False
    assert not check.ok and check.reason() == "blocked by robots.txt"
    assert check.latest is not None and check.latest.year == 2026


def test_html_page_is_not_a_feed() -> None:
    check = _parse_feed("https://x/feed", _response(b"<html><body>Not found</body></html>"))
    assert check.entries == 0 and check.error


def test_failed_source_written_inactive_with_reason() -> None:
    bad = CandidateResult("city_am", "City AM", "rss", "uk", 2, 3, [], "full")
    bad.checks.append(FeedCheck(url="https://www.cityam.com/feed/", robots_allowed=False,
                                error="blocked"))
    bad.notes = "robots"
    good = CandidateResult("bbc", "BBC", "rss", "uk", 2, 3, [], "full",
                           chosen_url="https://feeds.bbci.co.uk/x.xml")
    doc = build_sources_document([bad, good])
    parsed = SourcesFile.model_validate(doc)
    by_id = {s.source_id: s for s in parsed.sources}
    assert by_id["city_am"].active is False and by_id["city_am"].url
    assert by_id["bbc"].active is True


def test_stale_feed_detected() -> None:
    from datetime import UTC, datetime

    from ai_news.jobs.audit_sources import _is_stale

    now = datetime(2026, 11, 20, tzinfo=UTC)
    assert _is_stale(datetime(2021, 11, 1, tzinfo=UTC), now)
    assert not _is_stale(datetime(2026, 10, 1, tzinfo=UTC), now)
