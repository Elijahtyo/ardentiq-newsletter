"""Phase 0 gate: render a sample briefing, and optionally send it to one address.

    python -m ai_news.jobs.briefing_smoke --dry-run   # write files only
    python -m ai_news.jobs.briefing_smoke             # send to BRIEFING_TEST_TO

This never mails the client list. It uses ``BRIEFING_TEST_TO`` (a single
address) so the sending path can be proven without contacting subscribers.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ai_news.briefing.models import Briefing, BriefingItem, BriefingSection
from ai_news.briefing.send import FileSender, GraphSender, parse_recipients
from ai_news.config import load_settings, repo_root
from ai_news.graph import GraphConfig
from ai_news.logging_setup import configure_logging, get_logger

log = get_logger(__name__)

SAMPLE_ID = "phase0-sample"


def sample_briefing(now: datetime) -> Briefing:
    """A fixed example. No feed, no model and no network call is involved."""
    return Briefing(
        digest_id=SAMPLE_ID,
        headline="What changed in AI this week, and what it costs a small UK firm",
        window_start=now - timedelta(days=3),
        window_end=now,
        intro=(
            "This is a sample issued by the Phase 0 check. It proves the briefing renders "
            "and sends. Real issues are built from fetched news, not from this text."
        ),
        sections=[
            BriefingSection(
                heading="UK",
                items=[
                    BriefingItem(
                        cluster_id="sample-uk",
                        title="A regulator publishes guidance (sample)",
                        summary=(
                            "This is placeholder text for the layout check. It is not a claim "
                            "about any real organisation."
                        ),
                        why_it_matters="Shows where a one-line SME takeaway sits in the email.",
                        urls=["https://example.com/guidance"],
                    )
                ],
            ),
            BriefingSection(
                heading="Global",
                items=[
                    BriefingItem(
                        cluster_id="sample-global",
                        title="A model release (sample)",
                        summary=(
                            "Second placeholder item so a section with one item can be checked."
                        ),
                        why_it_matters="Confirms spacing and numbering across sections.",
                        urls=["https://example.com/release"],
                    )
                ],
            ),
        ],
        watch=["Sample date: an entry here shows the watch list block."],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="render to files, send nothing")
    args = parser.parse_args(argv)
    configure_logging()

    settings = load_settings()
    now = datetime.now(UTC)
    briefing = sample_briefing(now)
    out_dir = repo_root() / settings.briefing.out_dir

    if args.dry_run or not os.environ.get(settings.briefing.test_recipients_env):
        recipients = ["test@example.com"]
        sender = FileSender(out_dir, settings.briefing.subject_prefix, settings.briefing.footer)
        message = sender.send(briefing, recipients)
        print(f"OK: {message}")
        if not args.dry_run:
            print(
                f"note: {settings.briefing.test_recipients_env} is not set, so nothing was sent"
            )
        return 0

    recipients = parse_recipients(os.environ[settings.briefing.test_recipients_env])
    if len(recipients) != 1:
        print(
            f"refusing to send: {settings.briefing.test_recipients_env} must hold exactly "
            f"one address, found {len(recipients)}"
        )
        return 1
    sender = GraphSender(
        GraphConfig.from_env(), settings.briefing.subject_prefix, settings.briefing.footer
    )
    print(f"OK: {sender.send(briefing, recipients)}")
    log.info("briefing_smoke.sent", extra={"to": recipients[0]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["SAMPLE_ID", "Path", "main", "sample_briefing"]
