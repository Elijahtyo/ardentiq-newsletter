"""Phase 0 gate: create the schema and tables, then MERGE one test row.

    python -m ai_news.jobs.db_smoke --dry-run   # print the SQL, connect to nothing
    python -m ai_news.jobs.db_smoke             # create tables, write and read back a row

The test row goes into pipeline_runs with run_id 'phase0-smoke' and status
'smoke_test'. Because it is a MERGE, re-running updates the row instead of adding
another one, which also proves the idempotent-write path works. Later runs only
read rows with status 'succeeded', so the test row never affects a news window.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from ai_news.config import load_settings
from ai_news.logging_setup import configure_logging, get_logger
from ai_news.storage import databricks as db

log = get_logger(__name__)

SMOKE_RUN_ID = "phase0-smoke"


def merge_statement(schema: str) -> str:
    return f"""
MERGE INTO {schema}.pipeline_runs AS t
USING (SELECT :run_id AS run_id, CAST(:ts AS TIMESTAMP) AS ts, :errors AS errors) AS s
ON t.run_id = s.run_id
WHEN MATCHED THEN UPDATE SET
  t.started_at = s.ts, t.finished_at = s.ts, t.status = 'smoke_test', t.errors = s.errors
WHEN NOT MATCHED THEN INSERT
  (run_id, started_at, finished_at, status,
   items_fetched, items_kept, tokens_in, tokens_out, errors)
  VALUES (s.run_id, s.ts, s.ts, 'smoke_test', 0, 0, 0, 0, s.errors)
""".strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print SQL, write nothing")
    args = parser.parse_args(argv)
    configure_logging()

    settings = load_settings()
    schema = db.qualified_schema(settings.databricks)
    statements = db.ddl_statements(settings.databricks)
    merge = merge_statement(schema)
    now = datetime.now(UTC).replace(microsecond=0)
    params = {
        "run_id": SMOKE_RUN_ID,
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "errors": json.dumps(["phase0 smoke test row; safe to ignore"]),
    }

    if args.dry_run:
        print(f"-- dry run against {schema}; nothing executed")
        for statement in statements:
            print(statement + "\n;")
        print(merge + "\n;")
        print(f"-- params: {params}")
        return 0

    with db.connect(settings.databricks) as conn:
        for statement in statements:
            db.execute(conn, statement)
        log.info("db_smoke.ddl_ok", extra={"schema": schema, "statements": len(statements)})
        db.execute(conn, merge, params)
        rows = db.execute(
            conn,
            f"SELECT run_id, status, finished_at FROM {schema}.pipeline_runs "
            "WHERE run_id = :run_id",
            {"run_id": SMOKE_RUN_ID},
        )
        tables = db.execute(conn, f"SHOW TABLES IN {schema}")

    if len(rows) != 1:
        log.error("db_smoke.readback_failed", extra={"rows": len(rows)})
        return 1
    found = sorted(row[1] for row in tables)
    missing = sorted(set(db.TABLES) - set(found))
    log.info(
        "db_smoke.ok",
        extra={"row": [str(value) for value in rows[0]], "tables": found, "missing": missing},
    )
    print(f"OK: test row written and read back from {schema}.pipeline_runs: {tuple(rows[0])}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
