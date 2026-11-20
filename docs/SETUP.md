# Phase 0 setup

Do these steps in order. Each one ends with a check you can run.

## 1. GitHub repository

Repo: **https://github.com/Elijahtyo/ardentiq-newsletter** (private). Secrets and variables go under Settings → Secrets and variables → Actions on that repo.

1. The repo was created with its own README commit, so the first push merges that history in (this folder's README wins):
   ```
   git remote add origin https://github.com/Elijahtyo/ardentiq-newsletter.git
   git fetch origin
   git merge origin/main --allow-unrelated-histories -X ours
   git push -u origin main
   ```
3. The `ci` workflow runs on push. It should go green (ruff and pytest).

## 2. Databricks (Free Edition for prototyping only)

Workspace: **AI News Pipeline**, signed in as `elijah.olutayo@ardentiq.co.uk`. All connection values below come from that workspace.

Free Edition may not be used commercially. Before the pipeline feeds a real company page, move to a paid workspace or a trial. That move only changes the four values below.

No Delta Sharing (open sharing) identifier is needed. The pipeline writes through a SQL warehouse with a personal access token, and sharing tables out of the workspace isn't part of the design.

1. **SQL warehouse.** Go to SQL Warehouses, open the starter warehouse, then Connection details. Copy:
   - Server hostname → secret `DATABRICKS_HOST` (with or without `https://`)
   - HTTP path → secret `DATABRICKS_HTTP_PATH`
2. **Token.** Go to User settings, then Developer, then Access tokens, and generate a token with a 90-day lifetime. Store it as secret `DATABRICKS_TOKEN`. Put the expiry date in your calendar.
3. **Catalog. Please check this one.** Free Edition workspaces usually come with a catalog called `workspace`, not `main`. In Catalog Explorer, see which catalog you can create schemas in. If it isn't `main`, add a repository **variable** (not a secret) `DATABRICKS_CATALOG` with that name. The schema defaults to `ai_news`.

Check: the `phase0` workflow's "Databricks test write" step creates the 8 tables and MERGEs one row into `pipeline_runs`.

> Free Edition limits outbound traffic *from* its own compute. This pipeline goes the other way: GitHub Actions connects *in* to the SQL warehouse over HTTPS. That should work. If it doesn't, the smoke step fails, and the brief says to stop and report at that point.

## 3. Microsoft 365 mailbox (Graph, app-only)

You need a mailbox the newsletters go to (a shared mailbox is fine and needs no licence), for example `ai-news@yourco.co.uk`. Subscribe the newsletters to it.

### 3a. App registration (Entra admin centre)
1. Go to App registrations, then New registration. Name it `ai-news-pipeline`, single tenant, no redirect URI.
2. Copy the **Application (client) ID** to secret `MS_CLIENT_ID` and the **Directory (tenant) ID** to secret `MS_TENANT_ID`.
3. Go to Certificates & secrets, then New client secret (12 months). Copy the **Value** to secret `MS_CLIENT_SECRET`. Note the expiry date.

### 3b. Restrict the app to one mailbox. This differs from the brief, so please confirm.
The brief says "Mail.Read application permission restricted to the one mailbox". Microsoft now recommends **RBAC for Applications** in Exchange Online for this. The older Application Access Policies still work, but they are legacy. The main difference is that with RBAC for Applications you **do not** grant Mail.Read in Entra. An Entra grant applies to every mailbox in the tenant and would override the restriction.

**Recommended (RBAC for Applications).** In Exchange Online PowerShell (`Connect-ExchangeOnline`), run:
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
**Mail.Send is new.** The brief says `check.yml` should email you when a digest is missing. Sending that email through Graph needs Mail.Send, scoped to the same mailbox, so the alert comes *from* `ai-news@`. If you'd rather not grant it, the alternative is a GitHub Actions failure notification. That needs no permission, but it is less visible.

**Legacy alternative:** grant Mail.Read and Mail.Send as *application* permissions in Entra, click Grant admin consent, then run `New-ApplicationAccessPolicy -AccessRight RestrictAccess -AppId $appId -PolicyScopeGroupId <mail-enabled security group containing only ai-news@>`.

Secrets: `MS_MAILBOX` = `ai-news@yourco.co.uk` and `ALERT_EMAIL_TO` = your own address.
Optional repository **variable** `MS_POLICY_PROBE_MAILBOX` = your own address. The live check then confirms the app is *denied* access to it.

Changes to the policy can take up to an hour to apply.

## 4. Anthropic

Create an API key in the Claude Console in a workspace dedicated to this pipeline, and set a monthly spend limit on it. Store it as secret `ANTHROPIC_API_KEY`. The live check calls `models.retrieve` for each configured model, which costs nothing.

## 5. Run the gate

Actions tab → `phase0` → Run workflow. Expected output:
```
[anthropic] OK: key valid; models available: claude-haiku-5-5, claude-sonnet-5-5
[databricks] OK: warehouse reachable as you@...; default catalog workspace
[graph] OK: read ai-news@... inbox (1 message sampled); you@... correctly denied (403)
OK: test row written and read back from workspace.ai_news.pipeline_runs: ('phase0-smoke', 'smoke_test', ...)
```

You can run the same checks locally. In PowerShell, set the variables, then run:
`python -m ai_news.jobs.check_secrets --live` and `python -m ai_news.jobs.db_smoke`.

## Secrets summary

| Name | Kind | Needed from |
| --- | --- | --- |
| ANTHROPIC_API_KEY | secret | Phase 0 |
| DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN | secret | Phase 0 |
| DATABRICKS_CATALOG, DATABRICKS_SCHEMA | variable (optional) | Phase 0 |
| MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET, MS_MAILBOX, ALERT_EMAIL_TO | secret | Phase 0 |
| MS_POLICY_PROBE_MAILBOX | variable (optional) | Phase 0 |
| LINKEDIN_ACCESS_TOKEN, LINKEDIN_REFRESH_TOKEN, LINKEDIN_ORG_URN | secret | Phase 5 |

Credentials that expire: Databricks token (90 days), Entra client secret (12 months), LinkedIn token (see LINKEDIN_APPLICATION.md). From Phase 3 onwards, the pipeline will warn before each of these expires.
