"""Deliver a briefing.

Two senders, deliberately small:

``FileSender``
    renders to ``briefing/out/<digest_id>.html`` and ``.txt``. Default, and what
    ``--dry-run`` uses. Nothing leaves the machine.
``GraphSender``
    posts the rendered message through Microsoft Graph ``sendMail`` from the
    newsletter mailbox. One request per briefing, all recipients in BCC so the
    client list is never disclosed between subscribers.

Recipients are personal data, so they are supplied as a GitHub Actions secret
(``BRIEFING_RECIPIENTS``) and never committed to the repository.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from ai_news.briefing.models import Briefing
from ai_news.briefing.render import render_html, render_text, subject_for
from ai_news.graph import GraphConfig, send_mail

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_SEPARATORS = re.compile(r"[,;\n]")


class SendError(RuntimeError):
    """Raised when a briefing cannot be delivered."""


def parse_recipients(raw: str) -> list[str]:
    """Split a delimited list into unique, validated addresses.

    Accepts commas, semicolons and newlines so the same secret works whether it
    was pasted from Excel, Outlook or a CSV.
    """
    seen: set[str] = set()
    recipients: list[str] = []
    for chunk in _SEPARATORS.split(raw):
        address = chunk.strip().strip('"').strip("'")
        if not address:
            continue
        if not _EMAIL.match(address):
            raise SendError(f"not a valid email address: {address!r}")
        key = address.lower()
        if key in seen:
            continue
        seen.add(key)
        recipients.append(address)
    if not recipients:
        raise SendError("the client list is empty")
    return recipients


def build_sendmail_payload(
    *,
    sender: str,
    recipients: list[str],
    subject: str,
    html: str,
    text: str,
) -> dict:
    """The exact JSON body for Graph ``sendMail``, isolated so it can be tested."""
    if not recipients:
        raise SendError("refusing to send to nobody")
    return {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [],
            "bccRecipients": [{"emailAddress": {"address": address}} for address in recipients],
        },
        "saveToSentItems": True,
    }


class BriefingSender(Protocol):
    def send(self, briefing: Briefing, recipients: list[str]) -> str: ...


class FileSender:
    """Writes the rendered briefing to disk and sends nothing."""

    def __init__(self, out_dir: Path, subject_prefix: str, footer: str = "") -> None:
        self.out_dir = Path(out_dir)
        self.subject_prefix = subject_prefix
        self.footer = footer

    def send(self, briefing: Briefing, recipients: list[str]) -> str:
        if not recipients:
            raise SendError("refusing to send to nobody")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stem = self.out_dir / briefing.digest_id
        html_path = stem.with_suffix(".html")
        text_path = stem.with_suffix(".txt")
        html_path.write_text(render_html(briefing, self.footer), encoding="utf-8")
        text_path.write_text(render_text(briefing, self.footer), encoding="utf-8")
        subject = subject_for(briefing, self.subject_prefix)
        return (
            f"dry run: wrote {html_path} and {text_path} for {len(recipients)} "
            f"recipient(s); subject {subject!r}"
        )


class GraphSender:
    """Sends through Microsoft Graph from the newsletter mailbox."""

    def __init__(self, config: GraphConfig, subject_prefix: str, footer: str = "") -> None:
        self.config = config
        self.subject_prefix = subject_prefix
        self.footer = footer

    def send(self, briefing: Briefing, recipients: list[str]) -> str:
        payload = build_sendmail_payload(
            sender=self.config.mailbox,
            recipients=recipients,
            subject=subject_for(briefing, self.subject_prefix),
            html=render_html(briefing, self.footer),
            text=render_text(briefing, self.footer),
        )
        send_mail(self.config, payload)
        return (
            f"sent {briefing.digest_id} to {len(recipients)} recipient(s) "
            f"from {self.config.mailbox}"
        )
