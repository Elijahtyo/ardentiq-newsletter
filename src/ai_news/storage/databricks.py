"""Thin wrapper over databricks-sql-connector.

Talks to a SQL warehouse over HTTPS, so it works from GitHub Actions regardless of
the workspace's own outbound-internet restrictions.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from typing import Any

from ai_news.config import ConfigError, DatabricksSettings

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# The news/digest side only. LinkedIn drafts are deliberately not stored in
# Databricks: they live under linkedin/ in the repository, so no posting content
# or approval history passes through the Free Edition account.
TABLES = (
    "sources",
    "raw_items",
    "items_enriched",
    "digests",
    "digest_items",
    "pipeline_runs",
)


def _check_ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ConfigError(f"invalid catalog or schema name: {name!r}")
    return name


def qualified_schema(settings: DatabricksSettings) -> str:
    return f"{_check_ident(settings.catalog)}.{_check_ident(settings.schema_name)}"


def ddl_statements(settings: DatabricksSettings) -> list[str]:
    """Statements from schema.sql with the configured catalog.schema filled in."""
    text = resources.files("ai_news.storage").joinpath("schema.sql").read_text(encoding="utf-8")
    text = text.replace("{schema}", qualified_schema(settings))
    statements: list[str] = []
    for chunk in re.split(r"^;\s*$", text, flags=re.MULTILINE):
        body = "\n".join(
            line for line in chunk.splitlines() if not line.lstrip().startswith("--")
        ).strip()
        if body:
            statements.append(body)
    return statements


def server_hostname(host: str) -> str:
    return re.sub(r"^https?://", "", host).rstrip("/")


@contextmanager
def connect(settings: DatabricksSettings) -> Iterator[Any]:
    from databricks import sql  # imported lazily so tests need no warehouse

    token = os.environ.get(settings.token_env)
    if not token:
        raise ConfigError(f"environment variable {settings.token_env} is not set")
    conn = sql.connect(
        server_hostname=server_hostname(settings.host),
        http_path=settings.http_path,
        access_token=token,
        user_agent_entry="ai-news-pipeline",
    )
    try:
        yield conn
    finally:
        conn.close()


def execute(conn: Any, statement: str, params: dict[str, Any] | None = None) -> list[Any]:
    with conn.cursor() as cursor:
        cursor.execute(statement, params or {})
        try:
            return cursor.fetchall()
        except Exception:  # noqa: BLE001 - DDL/MERGE return no result set
            return []
