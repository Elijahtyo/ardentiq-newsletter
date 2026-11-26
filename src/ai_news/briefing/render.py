"""Render a briefing to plain text and HTML.

Every value is HTML-escaped on the way into the email. The text is untrusted at
every stage (feeds, email bodies, model output), so nothing is interpolated raw.
Markdown is deliberately not converted: the digest stage produces plain strings,
and a small renderer is easier to keep safe than a Markdown-to-HTML library.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from ai_news.briefing.models import Briefing

UK_DATE = "%A %d %B %Y"


def _window(briefing: Briefing) -> str:
    start = briefing.window_start.strftime("%d %b")
    end = briefing.window_end.strftime(UK_DATE)
    return f"{start} to {end}"


def render_text(briefing: Briefing, footer: str = "") -> str:
    """Plain-text alternative. Newsletters need one, and many readers prefer it."""
    lines: list[str] = [briefing.headline, _window(briefing), ""]
    if briefing.intro:
        lines += [briefing.intro, ""]
    for section in briefing.sections:
        if not section.items:
            continue
        lines += [section.heading.upper(), "-" * len(section.heading), ""]
        for index, item in enumerate(section.items, start=1):
            lines.append(f"{index}. {item.title}")
            lines.append(item.summary)
            lines.append(f"Why it matters: {item.why_it_matters}")
            if item.urls:
                lines.append("Source: " + item.urls[0])
            lines.append("")
    if briefing.watch:
        lines += ["WATCH LIST", "----------", ""]
        lines += [f"* {entry}" for entry in briefing.watch]
        lines.append("")
    if footer:
        lines += [footer, ""]
    return "\n".join(lines).rstrip() + "\n"


def render_html(briefing: Briefing, footer: str = "") -> str:
    """Self-contained HTML with inline styles; Outlook is the constraint."""
    parts: list[str] = [
        "<!doctype html>",
        '<html lang="en-GB"><head><meta charset="utf-8">',
        f"<title>{escape(briefing.headline)}</title></head>",
        '<body style="margin:0;padding:24px;background:#f6f6f4;'
        "font-family:Georgia,'Times New Roman',serif;color:#1d1d1b;\">",
        '<div style="max-width:640px;margin:0 auto;background:#ffffff;padding:32px;">',
        f'<h1 style="margin:0 0 4px;font-size:24px;line-height:1.25;">'
        f"{escape(briefing.headline)}</h1>",
        f'<p style="margin:0 0 24px;color:#5a5a55;font-size:14px;">{escape(_window(briefing))}</p>',
    ]
    if briefing.intro:
        parts.append(
            '<p style="font-size:16px;line-height:1.6;margin:0 0 24px;">'
            f"{escape(briefing.intro)}</p>"
        )
    for section in briefing.sections:
        if not section.items:
            continue
        parts.append(
            '<h2 style="font-size:13px;letter-spacing:0.08em;text-transform:uppercase;'
            f'border-top:1px solid #ddd;padding-top:16px;margin:28px 0 12px;">'
            f"{escape(section.heading)}</h2>"
        )
        for item in section.items:
            parts.append(
                '<div style="margin:0 0 20px;">'
                f'<h3 style="font-size:17px;margin:0 0 6px;line-height:1.3;">'
                f"{escape(item.title)}</h3>"
                f'<p style="margin:0 0 6px;font-size:15px;line-height:1.55;">'
                f"{escape(item.summary)}</p>"
                f'<p style="margin:0 0 6px;font-size:15px;line-height:1.55;color:#3d3d38;">'
                f"<strong>Why it matters:</strong> {escape(item.why_it_matters)}</p>"
            )
            for url in item.urls[:2]:
                parts.append(
                    f'<p style="margin:0;font-size:13px;">'
                    f'<a href="{escape(url, quote=True)}" style="color:#7a4b00;">'
                    f"{escape(url)}</a></p>"
                )
            parts.append("</div>")
    if briefing.watch:
        parts.append(
            '<h2 style="font-size:13px;letter-spacing:0.08em;text-transform:uppercase;'
            'border-top:1px solid #ddd;padding-top:16px;margin:28px 0 12px;">Watch list</h2>'
            '<ul style="margin:0 0 20px;padding-left:20px;font-size:15px;line-height:1.6;">'
        )
        parts += [f"<li>{escape(entry)}</li>" for entry in briefing.watch]
        parts.append("</ul>")
    if footer:
        parts.append(
            '<p style="margin:24px 0 0;border-top:1px solid #ddd;padding-top:16px;'
            f'font-size:12px;color:#6b6b66;line-height:1.5;">{escape(footer)}</p>'
        )
    parts += ["</div>", "</body>", "</html>"]
    return "\n".join(parts)


def subject_for(briefing: Briefing, prefix: str) -> str:
    when: datetime = briefing.window_end
    return f"{prefix} — {when.strftime('%d %B %Y')}: {briefing.headline}"
