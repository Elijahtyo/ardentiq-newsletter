from __future__ import annotations

import re

from ai_news.config import load_settings
from ai_news.jobs.db_smoke import merge_statement
from ai_news.storage.databricks import TABLES, ddl_statements, server_hostname

ENV = {"DATABRICKS_HOST": "https://h", "DATABRICKS_HTTP_PATH": "/p"}


def test_all_tables_created_with_comments() -> None:
    statements = ddl_statements(load_settings(environ=ENV).databricks)
    pattern = re.compile(r"TABLE IF NOT EXISTS main\.ai_news\.(\w+)")
    created = {m.group(1) for s in statements if (m := pattern.search(s))}
    assert created == set(TABLES)
    assert created == {
        "sources",
        "raw_items",
        "items_enriched",
        "digests",
        "digest_items",
        "pipeline_runs",
    }
    for statement in statements:
        assert "COMMENT" in statement
        if "CREATE TABLE" not in statement:
            continue
        columns = statement.split("(", 1)[1].rsplit(")", 1)[0]
        for line in filter(str.strip, columns.splitlines()):
            assert "COMMENT" in line, f"column without COMMENT: {line.strip()}"


def test_linkedin_content_is_never_stored_in_databricks() -> None:
    statements = ddl_statements(load_settings(environ=ENV).databricks)
    creates = [s for s in statements if "CREATE TABLE" in s]
    assert not any("linkedin" in statement.lower() for statement in creates)


def test_catalog_is_configurable() -> None:
    env = {**ENV, "DATABRICKS_CATALOG": "workspace"}
    statements = ddl_statements(load_settings(environ=env).databricks)
    assert all("main." not in s for s in statements)
    assert "workspace.ai_news.pipeline_runs" in merge_statement("workspace.ai_news")


def test_server_hostname_strips_scheme() -> None:
    assert server_hostname("https://dbc-1.cloud.databricks.com/") == "dbc-1.cloud.databricks.com"
