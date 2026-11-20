# Source audit

Generated 2026-11-20 by `python -m ai_news.jobs.audit_sources`.

- Candidates tried: **61**
- Verified: **39**
- Failed: **21**

A source counts as verified only if robots.txt allows it, the response is HTTP 200, and feedparser extracts at least one entry with a title and link.

## Verified

| Source | Tier | Region | Feed | Items | Newest |
| --- | --- | --- | --- | --- | --- |
| `accountancy_age` | 1 | uk | rss20 | 10 | 2026-11-19 |
| `aisi` | 1 | uk | atom10 | 11 | 2026-10-12 |
| `bank_of_england` | 1 | uk | rss20 | 50 | 2026-11-19 |
| `bcc` | 1 | uk | rss20 | 10 | 2026-11-19 |
| `fca` | 1 | uk | rss20 | 20 | — |
| `govuk_ai_keyword` | 1 | uk | atom10 | 20 | 2026-11-19 |
| `govuk_cma` | 1 | uk | atom10 | 20 | 2026-11-19 |
| `govuk_dbt` | 1 | uk | atom10 | 20 | 2026-11-02 |
| `govuk_dsit` | 1 | uk | atom10 | 20 | 2026-08-24 |
| `govuk_ico` | 1 | uk | atom10 | 14 | 2026-07-15 |
| `govuk_innovate_uk` | 1 | uk | atom10 | 20 | 2026-10-08 |
| `govuk_ukri` | 1 | uk | atom10 | 20 | 2026-10-13 |
| `htn` | 1 | uk | rss20 | 10 | 2026-11-19 |
| `legal_cheek` | 1 | uk | rss20 | 21 | 2026-11-19 |
| `logistics_manager` | 1 | uk | rss20 | 10 | 2026-11-19 |
| `nhs_england` | 1 | uk | rss20 | 10 | 2026-11-13 |
| `smallbusiness_uk` | 1 | uk | rss20 | 12 | 2026-11-18 |
| `ars_technica` | 2 | global | rss20 | 20 | 2026-11-19 |
| `bbc_business` | 2 | uk | rss20 | 53 | 2026-11-19 |
| `bbc_technology` | 2 | uk | rss20 | 21 | 2026-11-20 |
| `computer_weekly` | 2 | uk | rss20 | 20 | 2026-11-19 |
| `financial_times` | 2 | global | rss20 | 10 | 2026-11-19 |
| `guardian_technology` | 2 | uk | rss20 | 32 | 2026-11-19 |
| `mit_technology_review` | 2 | global | rss20 | 10 | 2026-11-19 |
| `sifted` | 2 | uk | rss20 | 24 | 2026-11-19 |
| `sky_technology` | 2 | uk | rss20 | 6 | 2026-11-19 |
| `tech_monitor` | 2 | uk | rss20 | 10 | 2026-11-19 |
| `techcrunch` | 2 | global | rss20 | 20 | 2026-11-20 |
| `the_verge` | 2 | global | atom10 | 10 | 2026-11-19 |
| `bens_bites` | 3 | global | rss20 | 20 | 2026-11-19 |
| `deepmind` | 3 | global | rss20 | 100 | 2026-11-18 |
| `exponential_view` | 3 | global | rss20 | 20 | 2026-11-16 |
| `import_ai` | 3 | global | rss20 | 20 | 2026-11-16 |
| `last_week_in_ai` | 3 | global | rss20 | 20 | 2026-11-11 |
| `meta_ai` | 3 | global | rss20 | 9 | 2026-11-18 |
| `microsoft_ai` | 3 | global | rss20 | 10 | 2026-11-17 |
| `openai_news` | 3 | global | rss20 | 1418 | 2026-11-19 |
| `rundown_ai` | 3 | global | rss20 | 50 | 2026-11-19 |
| `tldr_ai` | 3 | global | rss20 | 20 | 2026-11-19 |

## Failed — left inactive

| Source | Attempts |
| --- | --- |
| `ada_lovelace` | `https://www.adalovelaceinstitute.org/feed/` — no usable entries<br>`https://www.adalovelaceinstitute.org/rss/` — no usable entries |
| `anthropic_news` | `https://www.anthropic.com/rss.xml` — HTTP 404<br>`https://www.anthropic.com/news/rss.xml` — HTTP 404<br>`https://www.anthropic.com/feed.xml` — HTTP 404 |
| `city_am` | `https://www.cityam.com/feed/` — blocked (robots.txt parsed) |
| `consultancy_uk` | `https://www.consultancy.uk/rss/news` — no usable entries<br>`https://www.consultancy.uk/rss` — HTTP 404 |
| `cqc` | `https://www.cqc.org.uk/rss/news` — HTTP 404<br>`https://www.cqc.org.uk/news/rss` — HTTP 404 |
| `digital_health` | `https://www.digitalhealth.net/feed/` — HTTP 403 |
| `enterprise_nation` | `https://www.enterprisenation.com/feed/` — HTTP 404<br>`https://www.enterprisenation.com/rss/` — HTTP 404 |
| `finextra` | `https://www.finextra.com/rss/headlines.aspx` — blocked (robots.txt parsed)<br>`https://www.finextra.com/rss/news.aspx` — blocked (robots.txt parsed) |
| `fsb` | `https://www.fsb.org.uk/feed` — HTTP 404<br>`https://www.fsb.org.uk/rss` — HTTP 404 |
| `icaew` | `https://www.icaew.com/rss` — not a feed: <unknown>:22:146: not well-formed (invalid token)<br>`https://www.icaew.com/insights/rss` — HTTP 404 |
| `law_society_gazette` | `https://www.lawgazette.co.uk/rss` — HTTP 404<br>`https://www.lawgazette.co.uk/rss.xml` — HTTP 404 |
| `logistics_uk` | `https://logistics.org.uk/rss` — no usable entries<br>`https://logistics.org.uk/news/rss` — no usable entries<br>`https://logistics.org.uk/feed` — no usable entries |
| `management_today` | `https://www.managementtoday.co.uk/rss` — HTTP 404<br>`https://www.managementtoday.co.uk/rss/news` — HTTP 404 |
| `reuters_technology` | `https://www.reutersagency.com/feed/?best-topics=tech&post_type=best` — HTTP 404 |
| `techuk` | `https://www.techuk.org/feed` — HTTP 404<br>`https://www.techuk.org/news/rss` — HTTP 404 |
| `the_batch` | `https://www.deeplearning.ai/the-batch/feed/` — HTTP 404 |
| `the_register` | `https://www.theregister.com/headlines.atom` — blocked (robots.txt parsed) |
| `turing` | `https://www.turing.ac.uk/rss.xml` — HTTP 403<br>`https://www.turing.ac.uk/news/rss` — HTTP 403<br>`https://www.turing.ac.uk/feed` — HTTP 403 |
| `uk_finance` | `https://www.ukfinance.org.uk/rss.xml` — stale: newest item 2021-11-01<br>`https://www.ukfinance.org.uk/feed` — HTTP 404 |
| `uktn` | `https://www.uktech.news/feed` — blocked (robots.txt parsed)<br>`https://www.uktech.news/feed/` — blocked (robots.txt parsed) |
| `venturebeat` | `https://venturebeat.com/feed/` — HTTP 429 |

## Notes

- `content_policy: headline_only` marks sources where we store the headline and link only (Reuters, FT).
- A feed that parses but is stale (newest item months old) is still marked active; check the Newest column before trusting it.
