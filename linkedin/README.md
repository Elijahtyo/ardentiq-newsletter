# LinkedIn drafts

The LinkedIn branch of the pipeline. It shares the news calls with the briefing, and nothing else: **no draft, edit, approval or post goes into the briefing output or the state files.**

## Layout

```
drafts/<digest_id>.json   one file per digest run: hook, body, hashtags, status, timestamps
published.jsonl           append-only history, one line per published post
```

Both are committed to the repository. `DraftStore` (in `src/ai_news/linkedin/store.py`) is the only writer; it writes atomically and never resets a draft that is already approved.

## Approving

1. Open `drafts/<digest_id>.json`.
2. Read `post_text`. If you want changes, put them in `edited_text` — the publisher posts `edited_text` when present, otherwise `post_text`.
3. Set `status` to `approved` (or `rejected`, with a `reject_reason`).
4. Commit. That commit is your approval record.

Allowed moves are `draft → approved|rejected`, `approved → published|rejected`, and nothing out of `rejected` or `published`. `DraftStore.set_status` enforces them, so a typo cannot publish an unapproved draft.

Publishing only ever reads `status: approved`. The ManualPublisher renders those to a text file for pasting; `LinkedInPublisher` (Phase 5) posts them and records `post_urn`.

## Why files, not a database

- Approval is a pull request, which gives a reviewable history for free.
- The editor can fix a draft without any credentials.
- The weekly voice-tuning task diffs `post_text` against `edited_text` straight from these files.
- Drafts and client emails stay in separate places, so a briefing change cannot accidentally publish a post.
