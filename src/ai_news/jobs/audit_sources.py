"""Phase 0 source audit.

Tries every candidate feed URL in ``config/sources.candidates.yaml``, in order,
and decides which (if any) is usable for each source:

  * robots.txt must allow the path for our user agent
  * HTTP status must be 200
  * feedparser must parse it into at least one entry with a title and a link

The first candidate URL that passes becomes the source's URL. Sources where no
candidate passes are written to ``config/sources.yaml`` with ``active: false``
and the reason in ``notes``, so the failure is visible rather than silent.

Feed URLs rot constantly. Re-run this at any time; it is the same job CI uses.

    python -m ai_news.jobs.audit_sources              # audit and rewrite sources.yaml
    python -m ai_news.jobs.audit_sources --dry-run    # audit, print, write nothing
    python -m ai_news.jobs.audit_sources --only fca,bcc
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import feedparser
import httpx
import yaml

from ai_news.config import repo_root
from ai_news.logging_setup import configure_logging, get_logger

log = get_logger(__name__)

AUDIT_REPORT = Path("docs/SOURCE_AUDIT.md")
AUDIT_JSON = Path("reports/source_audit.json")


@dataclass(slots=True)
class FeedCheck:
    url: str
    status: int | None = None
    content_type: str | None = None
    robots_allowed: bool | None = None
    entries: int = 0
    latest: datetime | None = None
    feed_type: str | None = None
    error: str | None = None
    attempted: bool = True

    @property
    def ok(self) -> bool:
        return (
            self.attempted
            and self.status == 200
            and self.robots_allowed is not False
            and self.entries > 0
            and self.error is None
        )

    def reason(self) -> str:
        if self.error:
            return self.error
        if self.robots_allowed is False:
            return "blocked by robots.txt"
        if self.status != 200:
            return f"HTTP {self.status}"
        if self.entries == 0:
            return "parsed but contained no entries"
        return "ok"


@dataclass(slots=True)
class CandidateResult:
    source_id: str
    name: str
    type: str
    region: str | None
    tier: int
    uk_priority: int
    sectors: list[str]
    content_policy: str
    checks: list[FeedCheck] = field(default_factory=list)
    chosen_url: str | None = None
    notes: str | None = None

    @property
    def verified(self) -> bool:
        return self.chosen_url is not None


class RobotsCache:
    """Fetch and cache robots.txt per host. 404/410 means allow; 5xx means allow-with-caution.

    The robotparser spec treats an unreachable robots.txt as a full disallow.
    For a once-or-twice-weekly GET of a published feed that is needlessly strict,
    so a 5xx or a network error is recorded and allowed, and the audit output
    notes it so a human can look.
    """

    def __init__(self, client: httpx.AsyncClient, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent
        self._cache: dict[str, tuple[urllib.robotparser.RobotFileParser | None, str]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def allowed(self, url: str) -> tuple[bool, str]:
        parts = urllib.parse.urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._cache:
            lock = self._locks.setdefault(host, asyncio.Lock())
            async with lock:
                if host not in self._cache:
                    self._cache[host] = await self._load(host)
        parser, note = self._cache[host]
        if parser is None:
            return True, note
        return parser.can_fetch(self._user_agent, url), note

    async def _load(
        self, host: str
    ) -> tuple[urllib.robotparser.RobotFileParser | None, str]:
        robots_url = f"{host}/robots.txt"
        try:
            response = await self._client.get(robots_url, follow_redirects=True)
        except httpx.HTTPError as exc:
            return None, f"robots.txt unreachable ({type(exc).__name__}); allowed"
        if response.status_code >= 500:
            return None, f"robots.txt returned {response.status_code}; allowed"
        if response.status_code >= 400:
            return None, f"no robots.txt ({response.status_code}); allowed"
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser, "robots.txt parsed"


def _latest_entry(parsed: Any) -> datetime | None:
    for entry in parsed.entries:
        for key in ("published_parsed", "updated_parsed", "created_parsed"):
            value = entry.get(key)
            if value:
                try:
                    return datetime(*value[:6], tzinfo=UTC)
                except (TypeError, ValueError):
                    continue
    return None


def _parse_feed(url: str, response: httpx.Response) -> FeedCheck:
    check = FeedCheck(
        url=url,
        status=response.status_code,
        content_type=response.headers.get("content-type", "").split(";")[0].strip() or None,
    )
    if response.status_code != 200:
        return check
    parsed = feedparser.parse(response.content)
    usable = [
        entry
        for entry in parsed.entries
        if entry.get("title") and (entry.get("link") or entry.get("id"))
    ]
    check.entries = len(usable)
    check.latest = _latest_entry(parsed)
    check.feed_type = parsed.get("version") or ("html" if parsed.get("bozo") else None)
    if check.entries == 0:
        if parsed.get("bozo"):
            check.error = f"not a feed: {parsed.get('bozo_exception', 'unparseable')}"
        else:
            check.error = "no usable entries"
    return check


async def _check_url(
    client: httpx.AsyncClient,
    robots: RobotsCache,
    url: str,
    *,
    retries: int,
    backoff: float,
) -> FeedCheck:
    allowed, note = await robots.allowed(url)
    if not allowed:
        return FeedCheck(url=url, robots_allowed=False, error=f"blocked ({note})")

    last_error: str | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}".strip() or type(exc).__name__
            if attempt < retries:
                await asyncio.sleep(backoff * (2**attempt))
                continue
            return FeedCheck(url=url, robots_allowed=allowed, error=last_error)

        if response.status_code >= 500 and attempt < retries:
            await asyncio.sleep(backoff * (2**attempt))
            continue

        check = _parse_feed(url, response)
        check.robots_allowed = allowed
        return check

    return FeedCheck(url=url, robots_allowed=allowed, error=last_error or "unknown error")


STALE_AFTER_DAYS = 180


def _is_stale(latest: datetime, now: datetime | None = None) -> bool:
    """A feed whose newest item is months old has almost certainly been abandoned."""
    return ((now or datetime.now(UTC)) - latest).days > STALE_AFTER_DAYS


async def _audit_candidate(
    client: httpx.AsyncClient,
    robots: RobotsCache,
    candidate: dict[str, Any],
    *,
    semaphore: asyncio.Semaphore,
    retries: int,
    backoff: float,
) -> CandidateResult:
    result = CandidateResult(
        source_id=candidate["source_id"],
        name=candidate["name"],
        type=candidate.get("type", "rss"),
        region=candidate.get("region"),
        tier=int(candidate.get("tier", 3)),
        uk_priority=int(candidate.get("uk_priority", 0)),
        sectors=[str(s) for s in candidate.get("sectors") or []],
        content_policy=candidate.get("content_policy", "full"),
        notes=candidate.get("notes"),
    )

    if result.type == "email":
        # Mailbox sources are read through Graph and cannot be audited over HTTP.
        result.notes = result.notes or "Mailbox source; verified in Phase 1 via Graph."
        return result

    async with semaphore:
        for url in candidate.get("urls") or []:
            check = await _check_url(
                client, robots, url, retries=retries, backoff=backoff
            )
            result.checks.append(check)
            if check.ok and check.latest and _is_stale(check.latest):
                check.error = f"stale: newest item {check.latest.date().isoformat()}"
            if check.ok:
                result.chosen_url = url
                break

    if not result.verified:
        reasons = "; ".join(f"{c.url.split('//')[-1][:60]} -> {c.reason()}" for c in result.checks)
        result.notes = f"Phase 0 audit: no working feed. {reasons}"
    return result


async def run_audit(
    candidates: list[dict[str, Any]],
    *,
    timeout: float = 30.0,
    concurrency: int = 6,
    retries: int = 2,
    backoff: float = 1.5,
    user_agent: str = "ai-news-pipeline/0.1",
) -> list[CandidateResult]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*",
    }
    limits = httpx.Limits(max_connections=concurrency * 2)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout), headers=headers, limits=limits
    ) as client:
        robots = RobotsCache(client, user_agent)
        semaphore = asyncio.Semaphore(concurrency)
        return await asyncio.gather(
            *(
                _audit_candidate(
                    client,
                    robots,
                    candidate,
                    semaphore=semaphore,
                    retries=retries,
                    backoff=backoff,
                )
                for candidate in candidates
            )
        )


def build_sources_document(results: list[CandidateResult]) -> dict[str, Any]:
    """Turn audit results into the ``sources.yaml`` document."""
    ordered = sorted(results, key=lambda r: (r.tier, r.source_id))
    sources: list[dict[str, Any]] = []
    for result in ordered:
        # Inactive sources keep the first URL tried, so the failure is inspectable.
        url = result.chosen_url or (result.checks[0].url if result.checks else None)
        entry: dict[str, Any] = {
            "source_id": result.source_id,
            "name": result.name,
            "type": result.type,
            "url": url,
            "region": result.region,
            "tier": result.tier,
            "uk_priority": result.uk_priority,
            "sectors": result.sectors,
            "active": result.verified or result.type == "email",
        }
        if result.content_policy != "full":
            entry["content_policy"] = result.content_policy
        if result.notes:
            entry["notes"] = result.notes
        sources.append(entry)
    return {
        "version": 1,
        "updated": date.today().isoformat(),
        "sources": sources,
    }


def write_sources(document: dict[str, Any], path: Path) -> None:
    """Validate before writing: a bad entry must never reach the repo."""
    from ai_news.models import SourcesFile

    SourcesFile.model_validate(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Source registry. Generated by `python -m ai_news.jobs.audit_sources`.\n"
        "# Hand edits are allowed; re-running the audit overwrites them.\n"
        f"# Audited {document['updated']}.\n\n"
    )
    path.write_text(
        header + yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def report_markdown(results: list[CandidateResult]) -> str:
    verified = [r for r in results if r.verified]
    failed = [r for r in results if not r.verified and r.type != "email"]
    lines = [
        "# Source audit",
        "",
        f"Generated {date.today().isoformat()} by `python -m ai_news.jobs.audit_sources`.",
        "",
        f"- Candidates tried: **{len(results)}**",
        f"- Verified: **{len(verified)}**",
        f"- Failed: **{len(failed)}**",
        "",
        "A source counts as verified only if robots.txt allows it, the response is "
        "HTTP 200, and feedparser extracts at least one entry with a title and link.",
        "",
        "## Verified",
        "",
        "| Source | Tier | Region | Feed | Items | Newest |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in sorted(verified, key=lambda r: (r.tier, r.source_id)):
        check = next(c for c in result.checks if c.ok)
        newest = check.latest.date().isoformat() if check.latest else "—"
        feed_type = check.feed_type or "—"
        lines.append(
            f"| `{result.source_id}` | {result.tier} | {result.region or '—'} | "
            f"{feed_type} | {check.entries} | {newest} |"
        )

    if failed:
        lines += [
            "",
            "## Failed — left inactive",
            "",
            "| Source | Attempts |",
            "| --- | --- |",
        ]
        for result in sorted(failed, key=lambda r: r.source_id):
            attempts = "<br>".join(f"`{c.url}` — {c.reason()}" for c in result.checks)
            lines.append(f"| `{result.source_id}` | {attempts} |")

    lines += [
        "",
        "## Notes",
        "",
        "- `content_policy: headline_only` marks sources where we store the headline "
        "and link only (Reuters, FT).",
        "- A feed that parses but is stale (newest item months old) is still marked "
        "active; check the Newest column before trusting it.",
    ]
    return "\n".join(lines) + "\n"


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    candidates = raw.get("candidates") or []
    if not candidates:
        raise SystemExit(f"no candidates in {path}")
    return candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="print, write nothing")
    parser.add_argument("--only", default=None, help="comma-separated source_ids")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--fail-under", type=int, default=0,
                        help="exit non-zero if fewer than this many sources verify")
    args = parser.parse_args(argv)

    configure_logging()
    root = repo_root()
    candidates = _load_candidates(args.candidates or root / "config/sources.candidates.yaml")
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        candidates = [c for c in candidates if c["source_id"] in wanted]
        if not candidates:
            raise SystemExit(f"--only matched nothing: {sorted(wanted)}")

    log.info("audit.start", extra={"candidates": len(candidates)})
    results = asyncio.run(
        run_audit(
            candidates,
            timeout=args.timeout,
            concurrency=args.concurrency,
        )
    )

    verified = [r for r in results if r.verified]
    log.info(
        "audit.done",
        extra={"verified": len(verified), "failed": len(results) - len(verified)},
    )
    for result in sorted(results, key=lambda r: r.source_id):
        if result.type == "email":
            print(f"SKIP {result.source_id:26} mailbox source, checked via Graph")
            continue
        mark = "OK  " if result.verified else "FAIL"
        detail = (
            result.chosen_url
            if result.verified
            else " | ".join(f"{c.url} -> {c.reason()}" for c in result.checks)
        )
        print(f"{mark} {result.source_id:26} {detail}")

    document = build_sources_document(results)
    report = report_markdown(results)

    if args.dry_run:
        print("\n--- dry run: sources.yaml not written ---")
        print(yaml.safe_dump(document, sort_keys=False, width=100))
        return 0

    out_path = args.out or root / "config/sources.yaml"
    write_sources(document, out_path)
    report_path = root / AUDIT_REPORT
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    json_path = root / AUDIT_JSON
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {
                "generated": datetime.now(UTC).isoformat(timespec="seconds"),
                "results": [
                    {
                        "source_id": r.source_id,
                        "verified": r.verified,
                        "chosen_url": r.chosen_url,
                        "checks": [
                            {
                                "url": c.url,
                                "status": c.status,
                                "entries": c.entries,
                                "robots_allowed": c.robots_allowed,
                                "error": c.error,
                            }
                            for c in r.checks
                        ],
                    }
                    for r in results
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nwrote {out_path}")
    print(f"wrote {report_path}")
    if len(verified) < args.fail_under:
        print(
            f"ERROR: only {len(verified)} sources verified, need {args.fail_under}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
