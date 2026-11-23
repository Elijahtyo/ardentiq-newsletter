# AI news pipeline

Twice-weekly, UK-weighted AI news digest written to Databricks Delta tables, plus LinkedIn drafts for UK SMEs built from the same news calls. Runs on GitHub Actions.

**Two branches, one source.** The news calls feed two separate consumers that share no storage:

| Branch | Output | Storage |
| --- | --- | --- |
| Senior-staff digest | `digests`, `digest_items`, enriched items | Databricks Delta |
| LinkedIn drafts | `hook`, `body`, hashtags, approval state | Files under `linkedin/` — never Databricks |

The drafting job reads the digest produced by the same workflow run, so the LinkedIn branch neither writes to nor reads from Databricks. That keeps posting content and approval history out of the Free Edition workspace. It does **not** by itself change the Free Edition licence position: that edition may not be used commercially, so the digest side still needs a paid workspace or trial before go-live.

**Status: Phase 0.** Repo skeleton, source audit, Databricks schema and smoke write, secret checks, schedule guard. Setup steps: [docs/SETUP.md](docs/SETUP.md). LinkedIn application: [docs/LINKEDIN_APPLICATION.md](docs/LINKEDIN_APPLICATION.md). Source audit results: [docs/SOURCE_AUDIT.md](docs/SOURCE_AUDIT.md).

## Locations

| What | Where |
| --- | --- |
| GitHub repo (private) | https://github.com/Elijahtyo/ardentiq-newsletter |
| Databricks workspace | AI News Pipeline (Free Edition, account `elijah.olutayo@ardentiq.co.uk`) |
| Unity Catalog schema | `<catalog>.ai_news`, with the catalog set by the `DATABRICKS_CATALOG` variable (default `main`) |

## Local development

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\ruff check .
.venv\Scripts\pytest
```

## Jobs

| Command | What it does |
| --- | --- |
| `python -m ai_news.jobs.audit_sources [--dry-run]` | Tries every candidate in `config/sources.candidates.yaml` (robots.txt, HTTP, feed parse) and rewrites `config/sources.yaml` |
| `python -m ai_news.jobs.check_secrets [--live]` | Reports which secrets are present; `--live` calls each service read-only |
| `python -m ai_news.jobs.db_smoke [--dry-run]` | Creates schema and tables, MERGEs one test row into `pipeline_runs` |
| `python -m ai_news.jobs.guard [--force]` | Decides whether a scheduled trigger is the 09:00 London one |

## Layout

```
config/      settings.yaml (no secrets), sources.yaml (generated), sources.candidates.yaml
src/ai_news/ config, models, sources, logging_setup, jobs/, storage/, linkedin/
linkedin/    drafts/ (one JSON file per digest) and published.jsonl — the LinkedIn branch's store
tests/       mirrors src; fixtures/ holds recorded feeds
docs/        setup, LinkedIn application, source audit
```

Packages `ingest`, `process`, `llm` and `linkedin`, the `prompts/` folder, and the `digest`, `check` and `publish` workflows come in Phases 1 to 5.
