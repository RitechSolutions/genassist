# Salesforce Case Node

The **Salesforce Case** node lets a workflow builder push data from a workflow straight into
SalesForce as a **Case** (the CRM/Service-Cloud equivalent of a support ticket). It mirrors the
existing **Zendesk Ticket** node: drop it on the canvas, point it at a saved SalesForce
credential, map workflow values onto the Case fields, and at run time the node creates the Case
in your SalesForce org.

## Why it matters

GenAssist already ships a Zendesk node that turns a conversation/workflow outcome into a support
ticket. Customers who run **SalesForce** as their CRM/service system asked for the same native
capability so they no longer need external glue (manual export, third-party automation). The
Salesforce Case node gives builders a first-class, consistent experience: the same configuration
flow, the same per-tenant credential management, and the same pass-through behavior as the
Zendesk node.

## How to configure

### 1. Store SalesForce credentials (Configuration Vars)

SalesForce credentials are stored per tenant in **App Settings** (Configuration Vars), exactly
like Zendesk. Create a credential of type **Salesforce** with the three fields below. The secret
is encrypted at rest. Use the **Test Connection** button in the credential dialog to verify them.

| Field | Required | Notes |
|-------|----------|-------|
| `salesforce_instance_url` | yes | Your org / My Domain URL, e.g. `https://myorg.my.salesforce.com` (use the `.my.salesforce.com` host, **not** the `.my.salesforce-setup.com` Setup host) |
| `salesforce_client_id` | yes | Connected App **Consumer Key** |
| `salesforce_client_secret` | yes (encrypted) | Connected App **Consumer Secret** |

Authentication uses the **OAuth2 client-credentials grant** (app-level — no user login): the
connector posts to `{instance_url}/services/oauth2/token` with `grant_type=client_credentials`
and the client id/secret. The `access_token` and the `instance_url` **returned by that response**
are then used for the Case create (the org may redirect to a pod-specific host, which the
connector prefers over the configured URL).

**One-time SalesForce setup:** on the Connected App enable **OAuth Settings → Enable Client
Credentials Flow**, and under **Manage → Edit Policies → Client Credentials Flow** set a **Run
As** integration user (the Cases are created as that user). No username/password/security-token
is stored in GenAssist.

### 2. Add and configure the node

1. Open the **Workflow builder** (AI Agents → Workflows).
2. From the **integrations** section of the node palette, drag the **Salesforce Case** node onto
   the canvas.
3. Open its settings dialog and configure:
   - **Node Name** (optional)
   - **Configuration Vars** — the SalesForce credential to use (required), with the usual
     "create new" affordance.
   - **Subject** → Case `Subject` (required)
   - **Description** → Case `Description` (required)
   - **Labels** (optional) — a comma-separated tags input. Each label is assigned to the
     created Case as a SalesForce **Topic** (the node finds or creates the Topic by name, then
     links it via `TopicAssignment`). Requires **Topics for Objects** enabled on Case; label
     assignment is best-effort and never fails the Case creation.
   - **Custom Fields** — an optional dynamic **key/value** editor where each `key` is a Case
     field **API name** (e.g. `Priority`, `Origin`, `My_Custom_Field__c`) and `value` is the
     value to set. (This differs from the Zendesk node, which addresses fields by numeric id.)
4. Wire your flow into the node's **input** handle. Because it is a **pass-through** node, you
   can also wire its **output** handle to downstream nodes — creating the Case does not halt the
   run.
5. Save. The node reloads cleanly on reopen, like any other node.

## What it does (behavior)

When execution reaches the node, it validates the required fields, resolves the selected
credential within the run's tenant context, authenticates to SalesForce, and creates a Case via
`POST {instance_url}/services/data/v60.0/sobjects/Case`.

| Situation | Node result |
|-----------|-------------|
| Valid input, Case created | Success envelope `{"status": 200, "data": <SalesForce response>}` |
| Missing `subject` or `description` | `{"status": 400, "data": {"error": ...}}` — **no** SalesForce call is made |
| Auth / API / network failure (connector returns `None`) | `{"status": 500, "data": {"error": ...}}` |
| Any unhandled exception | `{"status": 500, "data": {"error": ...}}` |
| Downstream nodes wired after it | Still execute — the node does **not** halt the run |

After the Case is created, each **Label** is assigned as a Topic: the node finds or creates the
Topic by name, then inserts a `TopicAssignment` linking it to the Case. This runs per-label and
best-effort — if Topics aren't enabled or a label fails, it's logged and the created Case is
still returned.

## What it does not do / limitations

- **Create-only** for v1: it creates Cases. It does not read, search, or update existing
  SalesForce records, and is not a general-purpose REST/SOQL query node.
- No bulk operations or scheduled syncs.
- It does not build a bespoke SalesForce credential UI — it reuses the existing Configuration
  Vars (`app_settings`) mechanism.

## End-to-end flow

```
Workflow run (tenant + conversation thread_id)
        │
        ▼
Salesforce Case node ── validate subject/description
        │  resolve credential (AppSettingsService.get_by_id, tenant-scoped)
        ▼
SalesforceConnector
        ├─ POST {instance_url}/services/oauth2/token  (client_credentials grant)
        │     → access_token + instance_url
        ├─ POST {instance_url}/services/data/v60.0/sobjects/Case
        │     { Subject, Description, <custom Case field API names>: value }
        └─ per label: find/create Topic → POST TopicAssignment { EntityId: caseId, TopicId }
        │
        ▼
Run continues to any downstream nodes (pass-through)
```

## Under the hood (optional)

- **Connector:** `backend/app/modules/integration/salesforce.py` (`SalesforceConnector`):
  `_make_request` (httpx, `trust_env`, `raise_for_status`, errors wrapped in `HTTPException`),
  `_get_access_token` (OAuth2 client-credentials grant), `create_case` (returns the success
  envelope on 2xx and `None` on failure), `_assign_topics` / `_get_or_create_topic` (label →
  Topic assignment, best-effort), and a static async `test_connection`.
- **Node:** `backend/app/modules/workflow/engine/nodes/salesforce_tool_node.py`
  (`SalesforceToolNode`, type id `salesforceCaseNode`). Validates input, resolves the credential
  via `AppSettingsService`, **decrypts the encrypted `client_secret`** via `decrypt_key` before
  use, calls the connector (passing custom fields + labels), and owns the 400/500 error
  envelopes. (Decryption is required because `get_by_id` returns the stored values still
  encrypted — sending the ciphertext to SalesForce yields `invalid_client`.)
- **Dialog schema:** `backend/app/schemas/dynamic_form_schemas/nodes/salesforce_schema.py`
  (`SALESFORCE_CASE_NODE_DIALOG_SCHEMA`).
- **Registration:** engine registry in `workflow_engine.py`; label / dialog / handler schemas in
  `backend/app/schemas/dynamic_form_schemas/nodes/__init__.py` (handlers declare both an input
  `target` (`text`) and an output `source` (`any`)); and the node type is added to
  `SUPPORTED_NODE_TYPES` in `backend/app/api/v1/routes/workflows.py` (required by the
  builder's **Test node** and `dialog_schema` endpoints — a registry separate from the engine).
- **Credential type:** `"Salesforce"` added to the `app_settings_type_check` CHECK constraint
  (Alembic migration `00088_add_salesforce_app_setting_type.py`), the `AppSettingsType` Literal,
  and the App Settings form schemas.
- **Connection test:** `DataSourceService.test_connection` dispatches `salesforce` to
  `SalesforceConnector.test_connection`.
- **Tests:** `backend/tests/unit/workflow/test_salesforce_node.py`,
  `test_salesforce_node_registration.py`,
  `backend/tests/unit/integration/test_salesforce_connector.py`, and the SalesForce cases in
  `backend/tests/integration/app_settings/test_app_settings.py`.

## Related

- Spec: `specs/002-salesforce-node/spec.md`
- Plan: `specs/002-salesforce-node/plan.md`
- Data model (CHECK-constraint migration): `specs/002-salesforce-node/data-model.md`
