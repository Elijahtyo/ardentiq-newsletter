"""Microsoft Graph client (app-only, client credentials).

Used by two consumers and nothing else:

* ``ingest`` reads the newsletter mailbox (Mail.Read);
* ``briefing`` sends the finished briefing from the same mailbox (Mail.Send).

Both permissions are granted in Exchange with RBAC for Applications, scoped to
the one mailbox. See docs/SETUP.md. No permission is granted in Entra, because
an Entra application grant covers every mailbox in the tenant.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

BASE = "https://graph.microsoft.com/v1.0"
SCOPE = "https://graph.microsoft.com/.default"


class GraphError(RuntimeError):
    """Raised when Graph credentials are missing or a call fails."""


@dataclass(frozen=True, slots=True)
class GraphConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    mailbox: str

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> GraphConfig:
        env = os.environ if environ is None else environ
        missing = [
            name
            for name in ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET", "MS_MAILBOX")
            if not env.get(name)
        ]
        if missing:
            raise GraphError(f"missing environment variable(s): {', '.join(missing)}")
        return cls(
            tenant_id=env["MS_TENANT_ID"],
            client_id=env["MS_CLIENT_ID"],
            client_secret=env["MS_CLIENT_SECRET"],
            mailbox=env["MS_MAILBOX"],
        )


@lru_cache(maxsize=4)
def _cached_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    import msal  # lazy: tests and most jobs need no Microsoft SDK

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )
    result = app.acquire_token_for_client(scopes=[SCOPE])
    if "access_token" not in result:
        raise GraphError(
            f"token request failed: {result.get('error_description', result)}"
        )
    return str(result["access_token"])


def token(config: GraphConfig) -> str:
    """Application access token. Cached for the life of the process."""
    return _cached_token(config.tenant_id, config.client_id, config.client_secret)


def _client(config: GraphConfig):
    import httpx

    return httpx.Client(
        base_url=BASE,
        timeout=30,
        headers={"Authorization": f"Bearer {token(config)}"},
    )


def list_unread(config: GraphConfig, top: int = 1) -> list[dict]:
    """One page of the newsletter inbox, newest first."""
    with _client(config) as client:
        response = client.get(
            f"/users/{config.mailbox}/mailFolders/inbox/messages",
            params={
                "$top": str(top),
                "$select": "id,receivedDateTime,subject,from,body,hasAttachments",
                "$orderby": "receivedDateTime desc",
            },
        )
        response.raise_for_status()
        return response.json().get("value", [])


def send_mail(config: GraphConfig, payload: dict) -> None:
    """POST a ready Made message to /users/{mailbox}/sendMail."""
    with _client(config) as client:
        response = client.post(f"/users/{config.mailbox}/sendMail", json=payload)
        if response.status_code >= 400:
            raise GraphError(f"sendMail failed: {response.status_code} {response.text[:300]}")
