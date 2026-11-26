# Phase 0 setup

Do these steps in order. Each one ends with a check you can run. There is no database: the briefing is emailed, and run state is committed under `state/`.

## 1. GitHub repository

Repo: **https://github.com/Elijahtyo/ardentiq-newsletter** (private). Secrets and variables go under Settings → Secrets and variables → Actions on that repo.

The `ci` workflow runs on every push. It should go green (ruff and pytest).

## 2. Microsoft 365: one mailbox, two jobs

The newsletter mailbox both **receives** the source newsletters (Mail.Read) and **sends** the finished briefing (Mail.Send). Use a shared mailbox; it needs no licence.

### 2a. App registration (Entra admin centre)
1. App registrations → New registration. Name it `ai-news-pipeline`, single tenant, no redirect URI.
2. Copy the **Application (client) ID** to secret `MS_CLIENT_ID` and the **Directory (tenant) ID** to `MS_TENANT_ID`.
3. Certificates & secrets → New client secret (12 months). Copy the **Value** to `MS_CLIENT_SECRET`.

Do **not** add Mail permissions under API permissions. Access is granted in Exchange, scoped to the one mailbox; an Entra grant would cover every mailbox in the tenant and override the scope.

### 2b. Grant access with RBAC for Applications
In Exchange Online PowerShell (`Connect-ExchangeOnline`):
```powershell
$appId    = "<MS_CLIENT_ID>"
$objectId = "<Object ID from Entra > Enterprise applications > ai-news-pipeline>"
New-ServicePrincipal -AppId $appId -ObjectId $objectId -DisplayName "ai-news-pipeline"
New-ManagementScope -Name "ai-news-mailbox" `
  -RecipientRestrictionFilter "PrimarySmtpAddress -eq 'ai-news@yourco.co.uk'"
New-ManagementRoleAssignment -App $appId -Role "Application Mail.Read" -CustomResourceScope "ai-news-mailbox"
New-ManagementRoleAssignment -App $appId -Role "Application Mail.Send" -CustomResourceScope "ai-news-mailbox"
Test-ServicePrincipalAuthorization -Identity $appId -Resource ai-news@yourco.co.uk   # InScope = True
Test-ServicePrincipalAuthorization -Identity $appId -Resource you@yourco.co.uk       # InScope = False
```
Changes can take up to an hour to apply.

Secrets: `MS_MAILBOX` = `ai-news@yourco.co.uk`, `ALERT_EMAIL_TO` = your own address.
Optional variable `MS_POLICY_PROBE_MAILBOX` = your own address, so the live check proves the app is denied everything else.

## 3. Anthropic

Create an API key in the Claude Console in a workspace dedicated to this pipeline, and set a monthly spend limit. Store it as `ANTHROPIC_API_KEY`. The live check calls `models.retrieve`, which costs nothing.

## 4. Client list

Store the briefing recipients as secret **`BRIEFING_RECIPIENTS`**: one address per line, or comma/semicolon separated. Addresses are never committed — the repo is private, but the client list is personal data and belongs in a secret.

Also set **`BRIEFING_TEST_TO`** (secret): a single address you control. The Phase 0 check sends only here, never to the client list.

Sending stays off until `briefing.send_enabled` is flipped to `true` in `config/settings.yaml`.

## 5. Run the gate

Actions tab → `phase0` → Run workflow. Expected output:
```
[anthropic] OK: key valid; models available: claude-haiku-5-5, claude-sonnet-5-5
[graph]     OK: read ai-news@... inbox (1 message sampled); you@... correctly denied (403)
[briefing]  OK: client list valid: 14 recipient(s)
OK: dry run: wrote .../briefing/out/phase0-sample.html and ....txt for 1 recipient(s)
```

Locally, with the variables set:
`python -m ai_news.jobs.check_secrets --live` and `python -m ai_news.jobs.briefing_smoke --dry-run`.

To prove sending works, run `python -m ai_news.jobs.briefing_smoke` with `BRIEFING_TEST_TO` set. That sends one email to that address.

## Secrets summary

| Name | Kind | Needed from |
| --- | --- | --- |
| ANTHROPIC_API_KEY | secret | Phase 0 |
| MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET, MS_MAILBOX, ALERT_EMAIL_TO | secret | Phase 0 |
| MS_POLICY_PROBE_MAILBOX | variable (optional) | Phase 0 |
| BRIEFING_RECIPIENTS | secret | Phase 0 |
| BRIEFING_TEST_TO | secret (optional) | Phase 0 |
| LINKEDIN_ACCESS_TOKEN, LINKEDIN_REFRESH_TOKEN, LINKEDIN_ORG_URN | secret | Phase 5 |

Credentials that expire: Entra client secret (12 months), LinkedIn token (see LINKEDIN_APPLICATION.md). From Phase 3 onwards, the pipeline will warn before each expires.
