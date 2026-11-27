"""Phase 0 gate: confirm every secret is present and, with --live, that each works.

    python -m ai_news.jobs.check_secrets          # presence only, prints no values
    python -m ai_news.jobs.check_secrets --live   # also call each service

Live checks are read-only and cost nothing:
  * Anthropic: models.retrieve for every configured model id (free, no tokens)
  * Microsoft Graph: client-credentials token, then read one message id from the
    configured mailbox. If MS_POLICY_PROBE_MAILBOX is set, also confirm that a
    different mailbox is DENIED, proving the access policy restricts the app.
  * Briefing: parse the client list; report how many addresses it holds, never
    the addresses themselves.
  * LinkedIn: skipped until the Community Management API is approved.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from dataclasses import dataclass

from ai_news.config import load_settings
from ai_news.logging_setup import configure_logging, get_logger

log = get_logger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"


@dataclass(frozen=True, slots=True)
class Secret:
    name: str
    group: str
    required: bool = True
    note: str = ""


SECRETS: tuple[Secret, ...] = (
    Secret("ANTHROPIC_API_KEY", "anthropic"),
    Secret("MS_TENANT_ID", "graph"),
    Secret("MS_CLIENT_ID", "graph"),
    Secret("MS_CLIENT_SECRET", "graph"),
    Secret("MS_MAILBOX", "graph"),
    Secret("ALERT_EMAIL_TO", "graph"),
    Secret(
        "BRIEFING_RECIPIENTS",
        "briefing",
        required=False,
        note="needed only once briefing.send_enabled is true",
    ),
    Secret(
        "BRIEFING_TEST_TO",
        "briefing",
        required=False,
        note="optional; one address for the send test",
    ),
    Secret("LINKEDIN_ACCESS_TOKEN", "linkedin", required=False),
    Secret("LINKEDIN_ORG_URN", "linkedin", required=False),
)


def _required(settings: object) -> dict[str, bool]:
    """Which secrets must be present for *this* configuration.

    The recipient list is only required once sending is switched on, so a gate
    run does not fail simply because the client list is not finished yet.
    """
    briefing = getattr(settings, "briefing", None)
    sending = bool(briefing and briefing.send_enabled)
    return {"BRIEFING_RECIPIENTS": sending}


def presence(environ: dict[str, str] | None = None) -> dict[str, bool]:
    env = os.environ if environ is None else environ
    return {secret.name: bool(env.get(secret.name)) for secret in SECRETS}


def _check_anthropic() -> str:
    import anthropic

    settings = load_settings()
    client = anthropic.Anthropic(max_retries=2)
    model_ids = sorted(set(settings.models.model_dump().values()))
    for model_id in model_ids:
        client.models.retrieve(model_id)
    return f"key valid; models available: {', '.join(model_ids)}"


def _check_graph() -> str:
    import httpx

    from ai_news.graph import GraphConfig, list_unread, token

    config = GraphConfig.from_env()
    token(config)  # raises with a clear message if the app credentials are wrong
    messages = list_unread(config, top=1)
    note = f"read {config.mailbox} inbox ({len(messages)} message sampled)"

    probe = os.environ.get("MS_POLICY_PROBE_MAILBOX")
    if probe:
        with httpx.Client(timeout=30) as client:
            denied = client.get(
                f"{GRAPH}/users/{probe}/mailFolders/inbox/messages",
                params={"$top": "1"},
                headers={"Authorization": f"Bearer {token(config)}"},
            )
        if denied.status_code == 200:
            raise RuntimeError(f"app can read {probe}; the mailbox restriction is NOT in force")
        note += f"; {probe} correctly denied ({denied.status_code})"
    return note


def _check_briefing() -> str:
    from ai_news.briefing.send import SendError, parse_recipients

    settings = load_settings()
    if not settings.briefing.send_enabled:
        return "sending is off (briefing.send_enabled is false); client list not checked"
    secret = settings.briefing.recipients_env
    try:
        recipients = parse_recipients(os.environ.get(secret, ""))
    except SendError as exc:
        raise RuntimeError(f"{secret}: {exc}") from exc
    return f"client list valid: {len(recipients)} recipient(s)"


LIVE: dict[str, Callable[[], str]] = {
    "anthropic": _check_anthropic,
    "graph": _check_graph,
    "briefing": _check_briefing,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="call each service")
    parser.add_argument("--only", default=None, help="comma-separated groups to check live")
    args = parser.parse_args(argv)
    configure_logging()

    present = presence()
    settings = load_settings()
    conditionally_required = _required(settings)

    def is_required(secret: Secret) -> bool:
        return conditionally_required.get(secret.name, secret.required)

    failed = False
    missing: list[str] = []
    for secret in SECRETS:
        if present[secret.name]:
            state = "set"
        elif is_required(secret):
            state = "MISSING"
            missing.append(secret.name)
            failed = True
        elif secret.note:
            state = f"not set ({secret.note})"
        else:
            state = "not set (optional)"
        print(f"{secret.name:24} {state}")

    if missing:
        print()
        print("Required secrets not set: " + ", ".join(missing))
        print("Add them under Settings > Secrets and variables > Actions. See docs/SETUP.md.")

    if not args.live:
        print()
        print("GATE: missing required secrets" if failed else "GATE: all required secrets present")
        return 1 if failed else 0

    groups = list(LIVE) if not args.only else [g.strip() for g in args.only.split(",")]
    for group in groups:
        needed = [s.name for s in SECRETS if s.group == group and is_required(s)]
        if not all(present[name] for name in needed):
            print(f"[{group}] skipped: secrets missing")
            failed = True
            continue
        try:
            print(f"[{group}] OK: {LIVE[group]()}")
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            failed = True
            print(f"[{group}] FAILED: {type(exc).__name__}: {exc}")
            log.error("check_secrets.failed", extra={"group": group, "error": str(exc)})
    print("[linkedin] skipped: publishing not enabled until API approval")
    print()
    print("GATE: FAILED, see the lines above" if failed else "GATE: PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
