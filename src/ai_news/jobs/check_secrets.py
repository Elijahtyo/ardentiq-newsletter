"""Phase 0 gate: confirm every secret is present and, with --live, that each works.

    python -m ai_news.jobs.check_secrets          # presence only, prints no values
    python -m ai_news.jobs.check_secrets --live   # also call each service

Live checks are read-only and cost nothing:
  * Anthropic: models.retrieve for every configured model id (free, no tokens)
  * Databricks: SELECT 1 on the SQL warehouse
  * Microsoft Graph: client-credentials token, then read one message id from the
    configured mailbox. If MS_POLICY_PROBE_MAILBOX is set, also confirm that a
    different mailbox is DENIED, proving the access policy restricts the app.
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


SECRETS: tuple[Secret, ...] = (
    Secret("ANTHROPIC_API_KEY", "anthropic"),
    Secret("DATABRICKS_HOST", "databricks"),
    Secret("DATABRICKS_HTTP_PATH", "databricks"),
    Secret("DATABRICKS_TOKEN", "databricks"),
    Secret("MS_TENANT_ID", "graph"),
    Secret("MS_CLIENT_ID", "graph"),
    Secret("MS_CLIENT_SECRET", "graph"),
    Secret("MS_MAILBOX", "graph"),
    Secret("ALERT_EMAIL_TO", "graph"),
    Secret("LINKEDIN_ACCESS_TOKEN", "linkedin", required=False),
    Secret("LINKEDIN_ORG_URN", "linkedin", required=False),
)


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


def _check_databricks() -> str:
    from ai_news.storage import databricks as db

    settings = load_settings()
    with db.connect(settings.databricks) as conn:
        rows = db.execute(conn, "SELECT 1 AS ok, current_catalog(), current_user()")
    _, catalog, user = rows[0]
    return f"warehouse reachable as {user}; default catalog {catalog}"


def _graph_token() -> str:
    import msal

    app = msal.ConfidentialClientApplication(
        client_id=os.environ["MS_CLIENT_ID"],
        client_credential=os.environ["MS_CLIENT_SECRET"],
        authority=f"https://login.microsoftonline.com/{os.environ['MS_TENANT_ID']}",
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"token request failed: {result.get('error_description', result)}")
    return result["access_token"]


def _check_graph() -> str:
    import httpx

    token = _graph_token()
    headers = {"Authorization": f"Bearer {token}"}
    mailbox = os.environ["MS_MAILBOX"]
    url = f"{GRAPH}/users/{mailbox}/mailFolders/inbox/messages"
    with httpx.Client(timeout=30, headers=headers) as client:
        response = client.get(url, params={"$top": "1", "$select": "id,receivedDateTime"})
        response.raise_for_status()
        count = len(response.json().get("value", []))
        note = f"read {mailbox} inbox ({count} message sampled)"

        probe = os.environ.get("MS_POLICY_PROBE_MAILBOX")
        if probe:
            denied = client.get(
                f"{GRAPH}/users/{probe}/mailFolders/inbox/messages", params={"$top": "1"}
            )
            if denied.status_code == 200:
                raise RuntimeError(
                    f"app can read {probe}; the mailbox restriction is NOT in force"
                )
            note += f"; {probe} correctly denied ({denied.status_code})"
    return note


LIVE: dict[str, Callable[[], str]] = {
    "anthropic": _check_anthropic,
    "databricks": _check_databricks,
    "graph": _check_graph,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="call each service")
    parser.add_argument("--only", default=None, help="comma-separated groups to check live")
    args = parser.parse_args(argv)
    configure_logging()

    present = presence()
    failed = False
    for secret in SECRETS:
        ok = present[secret.name]
        if ok:
            state = "set"
        elif secret.required:
            state, failed = "MISSING", True
        else:
            state = "not set (optional until LinkedIn approves)"
        print(f"{secret.name:24} {state}")

    if not args.live:
        return 1 if failed else 0

    groups = list(LIVE) if not args.only else [g.strip() for g in args.only.split(",")]
    for group in groups:
        needed = [s.name for s in SECRETS if s.group == group and s.required]
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
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
