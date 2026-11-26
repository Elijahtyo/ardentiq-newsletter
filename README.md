# AI news pipeline

Twice-weekly, UK-weighted AI news **briefing**, emailed to a client list, plus LinkedIn drafts for UK SMEs built from the same news calls. Runs on GitHub Actions. No database.

**Two outputs, one source.** The news calls feed two consumers, and neither shares storage with the other:

| Output | What it is | Where it lives |
| --- | --- | --- |
| Client briefing | HTML and plain-text email, sent to the client list | Rendered to `briefing/out/`, then sent from the newsletter mailbox |
| LinkedIn drafts | Hook, body, hashtags, approval state | JSON files under `linkedin/` |

**Status: Phase 0, re-baselined.** The Databricks warehouse was removed on 26 November 2026. The digest is now an emailed briefing; run state lives in `state/`. Setup: [docs/SETUP.md](docs/SETUP.md). LinkedIn application: [docs/LINKEDIN_APPLICATION.md](docs/LINKEDIN_APPLICATION.md). Source audit: [docs/SOURCE_AUDIT.md](docs/SOURCE_AUDIT.md).

## Locations

| What | Where |
| --- | --- |
| GitHub repo (private) | https://github.com/Elijahtyo/ardentiq-newsletter |
| Client list | GitHub Actions secret `BRIEFING_RECIPIENTS` (never committed) |
| Run state | `state/pipeline_state.json` and `state/runs.jsonl` |

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
| `python -m ai_news.jobs.check_secrets [--live]` | Reports which secrets are present; `--live` calls each service read-only and validates the client list |
| `python -m ai_news.jobs.briefing_smoke [--dry-run]` | Renders a sample briefing to `briefing/out/`; without `--dry-run`, sends it to `BRIEFING_TEST_TO` only |
| `python -m ai_news.jobs.guard [--force]` | Decides whether a scheduled trigger is the 09:00 London one |

## Layout

```
config/       settings.yaml (no secrets), sources.yaml (generated), sources.candidates.yaml
src/ai_news/  config, models, sources, graph (Microsoft Graph), state, logging_setup
              briefing/ (models, render, send)   linkedin/ (models, store)   jobs/
linkedin/     drafts/ (one JSON file per digest) and published.jsonl
state/        pipeline_state.json (window) and runs.jsonl (run log)
tests/        mirrors src; fixtures/ holds recorded feeds
docs/         setup, LinkedIn application, source audit
```

## How a run works

1. Window start = `last_success_at` in `state/pipeline_state.json`, or 3 days back on a first run.
2. Fetch, dedupe, tag, summarise, rank — Phases 1 and 2.
3. Render the briefing and send it to the client list — Phase 2.
4. Draft LinkedIn posts from the same digest — Phase 4.
5. Write `last_success_at` **only** on success, so a failed run leaves the window where it was — Phase 3.
