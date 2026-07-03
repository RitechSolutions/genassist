# SalesForce Knowledge Article Sync

**SalesForce Knowledge Article Sync** lets an operator build a Knowledge Base out of the
**published SalesForce Knowledge articles** in their org. It mirrors the existing **Zendesk**
knowledge sync: create a Knowledge Base of type **SalesForce**, point it at a SalesForce Data
Source, and the platform pulls the articles in, indexes them for retrieval, keeps them current on
a schedule, and lets you sync on demand — with the same last-sync status/error visibility.

## Why it matters

GenAssist already syncs help-center articles from Zendesk into a Knowledge Base. Customers who
keep their support/help content in **SalesForce Knowledge** asked for parity so they no longer
have to export and re-upload articles by hand (which is error-prone and goes stale). This feature
reuses the proven Zendesk sync machinery, so SalesForce users get the same low-effort,
always-current ingestion path and the same Knowledge Base experience they already know.

## How to configure

### 1. Store SalesForce credentials (Configuration Vars)

Credentials live per tenant in **App Settings** (Configuration Vars) — the *same* SalesForce
credential the [Salesforce Case node](salesforce-node.md) uses. Create a credential of type
**Salesforce** (`salesforce_instance_url`, `salesforce_client_id`, `salesforce_client_secret` —
the secret is encrypted at rest) and authenticate via the **OAuth2 client-credentials grant**.
See the Case node doc for the one-time Connected App setup (Enable Client Credentials Flow + a
"Run As" user). You do **not** re-enter these secrets anywhere else.

### 2. Create a SalesForce Data Source

Under **Data Sources**, create a source of type **SalesForce**. Credentials are **not** typed
here — you select them from a **Configuration Vars** dropdown (the App Settings entry from step 1,
with a "create new" shortcut), exactly like the Gmail / Office 365 data sources. Then set the
sync options:

| Field | Required | Notes |
|-------|----------|-------|
| Configuration Vars (`app_settings_id`) | yes | The SalesForce App Settings credential to authenticate with |
| Article Content Field (`content_field`) | yes | API name of the Knowledge article's rich-text **body** field (org-specific, usually ends in `__c`). Ingested as the document body |
| Language (`language`) | no (advanced) | Restrict to one article `Language` (e.g. `en_US`). Leave blank to sync all |
| Data Category (`data_category`) | no (advanced) | A `WITH DATA CATEGORY` filter, e.g. `Region__c AT Europe__c`. Leave blank for none |

Use **Test Connection** to verify the credential resolves and authenticates.

### 3. Create the Knowledge Base

Under **Knowledge Base**, create a KB of type **SalesForce** and point it at the Data Source from
step 2. Configure it like a Zendesk KB:

- **Allow HTML content** — off (default) strips HTML tags from the article body; on keeps the
  rich-text markup.
- **Sync schedule** — enable automatic sync and set a cron expression (e.g. `*/15 * * * *`).
- **Sync Now** — trigger an immediate sync and see a summary of articles added / updated /
  deleted, plus the last-sync time, status, and any error.

> **Note:** unlike Zendesk, there is no "include unpublished" option — v1 syncs **published
> (Online)** articles only.

## What it does (behavior)

- Fetches **published/Online** SalesForce Knowledge articles (`Knowledge__kav`) from the org,
  optionally filtered by language and/or data category.
- Ingests each article's **Title + Summary + configured content field** into the Knowledge Base,
  converting rich-text/HTML the same way the Zendesk sync does.
- **Incremental reconciliation** on every sync: adds new articles, updates only articles whose
  `LastPublishedDate` advanced since the last sync (tracked per article), and deletes articles
  that are no longer in scope. Unchanged articles are skipped (not re-indexed).
- Records **last sync time, status** (success / success-with-warnings / error) and the **error
  message** on failure, shown in the Knowledge Base UI.
- Runs both **on a schedule** (Celery beat, every 15 min, honoring the KB's cron) and **on
  demand** (Sync Now).

## What it does not do / limitations

- **Inbound only** — it never writes articles back to SalesForce.
- **Published-only** in v1 (no drafts/archived; no include-unpublished toggle).
- Syncs **Knowledge articles only** — not Cases, Files, Attachments, or Chatter.
- No general-purpose SOQL/REST query surface; the Case node and the Zendesk sync are unchanged.

## End-to-end flow

1. Operator creates a SalesForce App Settings credential, a SalesForce Data Source (pointing at
   that credential + a content field), and a SalesForce Knowledge Base (pointing at the Data
   Source), then enables a schedule or clicks **Sync Now**.
2. Celery beat (or the manual trigger `GET /genagent/knowledge/kb-batch-tasks-execution?kb_id=…`)
   dispatches by KB type to the SalesForce importer, within the KB's **tenant** context.
3. The importer resolves the credential from Configuration Vars (decrypting the client secret),
   authenticates via OAuth2 client-credentials, and pages through the published articles.
4. It diffs the fetched articles against the documents already in the Knowledge Base and applies
   the add / update / delete changes, then records the sync status on the KB.
5. The Knowledge Base becomes retrievable context for any agent that uses it; the UI shows the
   last-sync summary.

## Under the hood (optional)

- **Credentials via Configuration Vars.** The Data Source stores only an `app_settings_id`
  reference — never the secret. At sync/test time the secret is resolved from App Settings and
  decrypted, exactly as the Case node does. Nothing sensitive is written to the Data Source or KB.
- **Connector.** `SalesforceConnector.fetch_knowledge_articles` runs a SOQL query over
  `Knowledge__kav` (`PublishStatus='Online'`, optional `Language`, optional `WITH DATA CATEGORY`)
  and paginates via the REST `nextRecordsUrl` cursor. The `content_field` and `data_category`
  inputs are validated to prevent SOQL injection.
- **Sync task.** `import_salesforce_articles_to_kb` mirrors the Zendesk task: tenant-scoped, RAG
  reconciliation keyed by `KB:{kb_id}#article_{KnowledgeArticleId}`, incremental tracking in the
  KB's `salesforce_article_updated_at` metadata, and safe failure handling (an API/fetch error
  records an error status and never deletes existing documents).
- **No database migration** — the SalesForce KB/Data Source reuse the existing `knowledge_bases`
  and `data_sources` tables (free-form `type` / `source_type` columns and their JSONB config).

## Related

- [Salesforce Case Node](salesforce-node.md) — the outbound counterpart (workflow → SalesForce Case).
- Zendesk knowledge sync — the inbound pattern this feature mirrors.
