# LinkedIn Community Management API application

Approval is slow, so submit early. The pipeline doesn't need it until Phase 5. Until then, ManualPublisher covers posting.

> I wrote this from what I know of LinkedIn's process. LinkedIn changes the portal and its policies without much notice. Before relying on any point marked **(confirm)**, check it against the live pages on developer.linkedin.com and in the product's access form.

## Before you apply

1. **Company Page.** You must be a **super admin** of the company Page.
2. **A new developer app, used only for this.** At developer.linkedin.com, go to Create app. Associate the app with the company Page, then have a Page admin verify the app from the Settings tab. LinkedIn requires Community Management API to be the **only product** on the app, so don't add "Sign In with LinkedIn" or "Share on LinkedIn" to it **(confirm)**.
3. **Legal entity details.** Have these ready: registered company name, address, website, a privacy policy URL on your domain, and a business email address on that domain. Free webmail addresses are commonly rejected.
4. **Access tiers.** Approval usually comes in stages: Development tier first, then an upgrade to Standard tier. The upgrade needs a screencast of the working integration **(confirm)**. The Phase 4 ManualPublisher flow is what you'd record.

## Scopes to request

| Scope | Why |
| --- | --- |
| `w_organization_social` | Create posts as the organisation (Phase 5 publisher) |
| `r_organization_social` | **Added beyond the brief.** Read your own organisation's posts and their social actions, so the `impressions` and `reactions` fields in the local drafts store (`linkedin/drafts/`) can be filled in. Without it those stay empty. Post impressions may also need the organisation share statistics endpoint **(confirm)**. |

No scraping and no browser automation. Every post goes through `POST /rest/posts`, with `author = urn:li:organization:<id>`.

## Draft use-case text (edit before pasting)

> **Company:** <Legal name>, <registered address>, <website>.
> **Use case:** We publish original commentary on artificial intelligence developments for UK small and medium-sized businesses on our own LinkedIn company Page (<page URL>). Our internal tool drafts posts from public news sources. A named member of our staff reviews and approves every post before it is published. The integration will only (1) create posts on our own organisation's Page and (2) read engagement on those posts to improve our content. We do not post on behalf of other organisations or members, do not access member data beyond the authenticated Page admin, and do not automate engagement (likes, comments, follows).
> **Volume:** about 2–6 posts per week, one organisation.
> **Users:** internal only; <n> Page admins.

## Tokens and expiry

- 3-legged OAuth, authorised by a Page admin. Access tokens currently last **60 days** (confirmed in LinkedIn's docs as of writing). Programmatic refresh tokens last **365 days** and are only issued to approved partner apps **(confirm once approved)**.
- When Phase 5 is built, the publisher will check the token's expiry (or call LinkedIn's token introspection endpoint) on every run and send an email warning 14 days before it expires.

## Gate checklist

- [ ] Developer app created and verified by the Page
- [ ] Community Management API access requested (Development tier)
- [ ] Application ID and date recorded here: ______
