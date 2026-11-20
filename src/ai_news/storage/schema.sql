-- Delta tables for the AI news pipeline. `{schema}` is replaced with catalog.schema
-- from config, so moving workspace is a config change. Every statement is
-- idempotent (CREATE ... IF NOT EXISTS). Statements are separated by a line
-- holding only ";".

CREATE SCHEMA IF NOT EXISTS {schema}
COMMENT 'UK-weighted AI news digest and LinkedIn drafting pipeline'
;
CREATE TABLE IF NOT EXISTS {schema}.sources (
  source_id   STRING        NOT NULL COMMENT 'Stable slug, primary key',
  name        STRING        COMMENT 'Display name',
  type        STRING        COMMENT 'rss, email or api',
  url         STRING        COMMENT 'Feed or API URL; null for mailbox sources',
  region      STRING        COMMENT 'uk or global',
  tier        INT           COMMENT '1 = UK official, trade and sector; 2 = news; 3 = labs and newsletters',
  uk_priority INT           COMMENT '0-3 weight applied when ranking UK relevance',
  sectors     ARRAY<STRING> COMMENT 'Focus sectors this source mainly covers',
  active      BOOLEAN       COMMENT 'False when the Phase 0 audit or later checks failed'
) USING DELTA
COMMENT 'Source registry, mirrored from config/sources.yaml'
;
CREATE TABLE IF NOT EXISTS {schema}.raw_items (
  item_id      STRING    NOT NULL COMMENT 'sha256 of the canonical URL, primary key',
  source_id    STRING    COMMENT 'FK to sources.source_id',
  url          STRING    COMMENT 'Canonical URL with tracking parameters removed',
  title        STRING    COMMENT 'Headline as published',
  published_at TIMESTAMP COMMENT 'Publisher timestamp (UTC), null if absent',
  fetched_at   TIMESTAMP COMMENT 'When the pipeline fetched it (UTC)',
  excerpt      STRING    COMMENT 'Short excerpt only; never full article text',
  content_hash STRING    COMMENT 'sha256 of title and excerpt, to detect edits'
) USING DELTA
COMMENT 'Every fetched item before dedupe and enrichment'
;
CREATE TABLE IF NOT EXISTS {schema}.items_enriched (
  cluster_id     STRING        NOT NULL COMMENT 'Stable id for a cluster of near-duplicate stories, primary key',
  item_ids       ARRAY<STRING> COMMENT 'raw_items in this cluster',
  topics         ARRAY<STRING> COMMENT 'Topic tags from the filter model',
  sectors        ARRAY<STRING> COMMENT 'Up to two focus sectors',
  is_uk          BOOLEAN       COMMENT 'True when the story is UK-specific',
  uk_relevance   INT           COMMENT '0-5',
  sme_relevance  INT           COMMENT '0-5',
  importance     INT           COMMENT '0-5',
  summary        STRING        COMMENT 'Two-sentence summary drawn only from fetched text',
  why_it_matters STRING        COMMENT 'One line on why it matters to UK SMEs',
  source_urls    ARRAY<STRING> COMMENT 'URLs the summary is grounded in',
  model          STRING        COMMENT 'Model id that produced the summary',
  prompt_version STRING        COMMENT 'Version of the prompt files used'
) USING DELTA
COMMENT 'One row per story cluster after tagging and summarising'
;
CREATE TABLE IF NOT EXISTS {schema}.digests (
  digest_id    STRING    NOT NULL COMMENT 'Primary key',
  run_ts       TIMESTAMP COMMENT 'When the digest was produced (UTC)',
  window_start TIMESTAMP COMMENT 'Start of the news window covered (UTC)',
  window_end   TIMESTAMP COMMENT 'End of the news window covered (UTC)',
  headline     STRING    COMMENT 'One-line digest headline',
  summary_md   STRING    COMMENT 'Opening summary, markdown',
  uk_md        STRING    COMMENT 'UK section, markdown',
  global_md    STRING    COMMENT 'Global section, markdown',
  sme_md       STRING    COMMENT 'SME angle grouped by sector, plus watch list, markdown',
  n_items      INT       COMMENT 'Number of clusters in the digest'
) USING DELTA
COMMENT 'Twice-weekly digests'
;
CREATE TABLE IF NOT EXISTS {schema}.digest_items (
  digest_id  STRING NOT NULL COMMENT 'FK to digests',
  cluster_id STRING NOT NULL COMMENT 'FK to items_enriched',
  section    STRING COMMENT 'uk, global, sme or watch',
  rank       INT    COMMENT 'Position within the digest, 1 = top'
) USING DELTA
COMMENT 'Which clusters appear in which digest, and where'
;
CREATE TABLE IF NOT EXISTS {schema}.linkedin_examples (
  example_id  STRING    NOT NULL COMMENT 'Primary key, derived from source_file',
  post_text   STRING    COMMENT 'Full text of a past post',
  format      STRING    COMMENT 'news_so_what, practical_tip, myth_vs_reality or question',
  sector      STRING    COMMENT 'Focus sector, or null for cross-sector',
  source_file STRING    COMMENT 'Path under prompts/examples/',
  added_at    TIMESTAMP COMMENT 'When loaded (UTC)',
  notes       STRING    COMMENT 'Free-text notes'
) USING DELTA
COMMENT 'Seed posts used as few-shot examples'
;
CREATE TABLE IF NOT EXISTS {schema}.linkedin_drafts (
  draft_id           STRING        NOT NULL COMMENT 'Primary key',
  digest_id          STRING        COMMENT 'FK to digests',
  status             STRING        COMMENT 'draft, approved, rejected or published',
  post_text          STRING        COMMENT 'Text as generated',
  edited_text        STRING        COMMENT 'Text after human edits; feeds the voice tuning loop',
  reject_reason      STRING        COMMENT 'Why it was rejected',
  sector             STRING        COMMENT 'Target sector, or null for cross-sector',
  source_cluster_ids ARRAY<STRING> COMMENT 'Digest clusters the post is grounded in',
  prompt_version     STRING        COMMENT 'Version of the prompt files used',
  model              STRING        COMMENT 'Model id that wrote the draft',
  impressions        BIGINT        COMMENT 'From LinkedIn once published',
  reactions          BIGINT        COMMENT 'From LinkedIn once published',
  created_at         TIMESTAMP     COMMENT 'UTC',
  approved_at        TIMESTAMP     COMMENT 'UTC',
  published_at       TIMESTAMP     COMMENT 'UTC',
  post_urn           STRING        COMMENT 'LinkedIn post URN once published'
) USING DELTA
COMMENT 'LinkedIn drafts and their approval state. Only approved drafts are ever published'
;
CREATE TABLE IF NOT EXISTS {schema}.pipeline_runs (
  run_id        STRING    NOT NULL COMMENT 'Primary key',
  started_at    TIMESTAMP COMMENT 'UTC',
  finished_at   TIMESTAMP COMMENT 'UTC',
  status        STRING    COMMENT 'running, succeeded, failed or smoke_test',
  items_fetched INT       COMMENT 'Raw items fetched this run',
  items_kept    INT       COMMENT 'Clusters kept after filtering',
  tokens_in     BIGINT    COMMENT 'Total input tokens across LLM calls',
  tokens_out    BIGINT    COMMENT 'Total output tokens across LLM calls',
  errors        STRING    COMMENT 'JSON array of non-fatal errors (failed sources etc.)'
) USING DELTA
COMMENT 'One row per pipeline run. The window for each run starts at the last succeeded run'
;
