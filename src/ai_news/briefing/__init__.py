"""The briefing: the pipeline's outward-facing output.

The twice-weekly digest is no longer stored in a warehouse. It is rendered to
HTML and plain text and emailed to the client list from the newsletter mailbox.
LinkedIn drafts remain a separate branch (see ``linkedin/``).
"""

from ai_news.briefing.models import Briefing, BriefingItem, BriefingSection
from ai_news.briefing.render import render_html, render_text
from ai_news.briefing.send import FileSender, GraphSender, parse_recipients

__all__ = [
    "Briefing",
    "BriefingItem",
    "BriefingSection",
    "FileSender",
    "GraphSender",
    "parse_recipients",
    "render_html",
    "render_text",
]
