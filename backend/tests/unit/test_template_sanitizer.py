"""Unit tests for the Template Marketplace graph sanitizer."""
import re
from pathlib import Path

import pytest

from app.services.template_sanitizer import (
    PER_TENANT_REF_FIELDS,
    PUBLISHER_ONLY_FIELDS,
    sanitize_graph,
    sanitize_template_graph,
    sanitize_test_input,
)


def _graph():
    nodes = [
        {
            "id": "n1",
            "type": "agentNode",
            "data": {
                "name": "Agent",
                "providerId": "prov-from-other-tenant",
                "selectedBases": ["kb-1", "kb-2"],
            },
        },
        {
            "id": "n2",
            "type": "externalAgentNode",
            "data": {
                "authToken": "super-secret",
                "authPassword": "pw",
                "authUsername": "user",
                "authHeader": "X-Api-Key",
                "endpoint": "https://example.com",
            },
        },
        {
            "id": "n3",
            "type": "mcpNode",
            "data": {"connectionConfig": {"url": "https://mcp", "token": "t"}},
        },
        {
            "id": "n4",
            "type": "ttsNode",
            "data": {"audioProviderId": "audio-1", "voiceProviderId": "voice-1"},
        },
        {
            "id": "n5",
            "type": "chatInputNode",
            "data": {
                "inputSchema": {
                    "message": {"type": "string", "required": True},
                    "apiKey": {"type": "string", "hidden": True, "defaultValue": "leak"},
                }
            },
        },
        {
            "id": "n6",
            "type": "sqlNode",
            "data": {"dataSourceId": "ds-1"},
        },
        {
            "id": "n7",
            "type": "webScraperNode",
            "data": {
                "url": "https://example.com",
                "headers": '{"Authorization": "Bearer super-secret"}',
            },
        },
    ]
    edges = [{"id": "e1", "source": "n1", "target": "n2"}]
    return nodes, edges


def test_blanks_per_tenant_references():
    nodes, edges = _graph()
    safe_nodes, _ = sanitize_graph(nodes, edges)
    by_id = {n["id"]: n["data"] for n in safe_nodes}
    assert by_id["n1"]["providerId"] is None
    assert by_id["n1"]["selectedBases"] == []
    assert by_id["n4"]["audioProviderId"] is None
    assert by_id["n4"]["voiceProviderId"] is None
    assert by_id["n6"]["dataSourceId"] is None


def test_strips_inline_secrets():
    nodes, edges = _graph()
    safe_nodes, _ = sanitize_graph(nodes, edges)
    by_id = {n["id"]: n["data"] for n in safe_nodes}
    for field in ("authToken", "authPassword", "authUsername", "authHeader"):
        assert field not in by_id["n2"]
    assert "endpoint" in by_id["n2"]  # non-secret field preserved
    assert "connectionConfig" not in by_id["n3"]
    # webScraperNode headers may carry Authorization tokens / cookies / API keys.
    assert "headers" not in by_id["n7"]
    assert by_id["n7"]["url"] == "https://example.com"  # non-secret field preserved


def test_strips_hidden_chat_input_defaults_only():
    nodes, edges = _graph()
    safe_nodes, _ = sanitize_graph(nodes, edges)
    schema = next(n for n in safe_nodes if n["id"] == "n5")["data"]["inputSchema"]
    assert "defaultValue" not in schema["apiKey"]  # hidden secret removed
    assert schema["message"]["required"] is True  # visible field untouched


def test_does_not_mutate_input_and_preserves_edges():
    nodes, edges = _graph()
    safe_nodes, safe_edges = sanitize_graph(nodes, edges)
    # original still has the secret (deep copy)
    assert nodes[1]["data"]["authToken"] == "super-secret"
    assert safe_edges == edges


def test_strips_secret_looking_fields_by_substring():
    # Node type whose secret lives under a key NOT in SECRET_DATA_FIELDS.
    nodes = [
        {
            "id": "n1",
            "type": "futureNode",
            "data": {
                "apiKey": "sk-leak",
                "clientSecret": "shhh",
                "accessToken": "at-leak",
                "endpoint": "https://example.com",  # benign, must survive
                "publicKey": "not-a-secret",         # benign, must survive
            },
        }
    ]
    safe_nodes, _ = sanitize_graph(nodes, [])
    data = safe_nodes[0]["data"]
    assert "apiKey" not in data
    assert "clientSecret" not in data
    assert "accessToken" not in data
    assert data["endpoint"] == "https://example.com"
    assert data["publicKey"] == "not-a-secret"


def test_sanitize_test_input_drops_hidden_and_secret_keys():
    nodes, _ = _graph()  # n5 marks apiKey as hidden
    test_input = {
        "message": "hello",          # visible → kept
        "apiKey": "sk-secret",       # hidden field → dropped
        "authToken": "t",            # secret-looking key → dropped
        "thread_id": "abc",          # benign → kept
    }
    safe = sanitize_test_input(nodes, test_input)
    assert safe == {"message": "hello", "thread_id": "abc"}


def test_sanitize_test_input_handles_none_and_empty():
    assert sanitize_test_input([], None) is None
    assert sanitize_test_input(None, {}) is None
    # A payload that is entirely secret collapses to None (no key stored).
    assert sanitize_test_input([], {"password": "x"}) is None


def test_sanitize_test_input_does_not_mutate_input():
    original = {"message": "hi", "apiKey": "sk"}
    nodes, _ = _graph()
    sanitize_test_input(nodes, original)
    assert original["apiKey"] == "sk"  # caller's dict untouched


def test_handles_none_and_empty():
    assert sanitize_graph(None, None) == ([], [])
    assert sanitize_graph([], []) == ([], [])


REF = "3f2b9a1c-0d4e-4c5f-9a6b-7c8d9e0f1a2b"
OTHER_REF = "8a7b6c5d-4e3f-4a1b-9c8d-7e6f5a4b3c2d"
GONE = object()
SAMPLE_ROWS = {"columns": ["email", "plan"], "preview": [{"email": "jane@example.com", "plan": "pro"}]}

# Every block type: its settings, and what cleaning changes (GONE = removed).
# Settings not named in the changes must come through unchanged.
BLOCKS = {
    "chatInputNode": (
        {
            "name": "Start",
            "inputSchema": {
                "message": {"type": "string", "required": True},
                "apiKey": {"type": "string", "defaultValue": "sk-live-1"},
                "plan": {"type": "string", "hidden": True, "defaultValue": "enc:abc"},
            },
        },
        {
            "inputSchema": {
                "message": {"type": "string", "required": True},
                "apiKey": {"type": "string"},
                "plan": {"type": "string", "hidden": True},
            }
        },
    ),
    "webhookTriggerNode": (
        {
            "name": "Webhook",
            "messagePath": "body.text",
            "fieldMappings": [{"key": "order", "path": "body.order"}],
            "samplePayload": '{"text": "Refund order 1", "email": "jane@example.com"}',
        },
        {"samplePayload": GONE},
    ),
    "chatOutputNode": ({"name": "Reply"}, {}),
    "routerNode": (
        {"name": "Route", "smartModeEnabled": True, "providerId": REF, "smartPrompt": "Pick one"},
        {"providerId": None},
    ),
    "switchNode": (
        {"name": "Switch", "smartModeEnabled": True, "providerId": REF, "cases": [{"value": "a"}]},
        {"providerId": None},
    ),
    "filterNode": ({"name": "Filter", "field": "status", "operator": "equals", "value": "open"}, {}),
    "loopNode": ({"name": "Loop", "mode": "forEach", "items": "{{input.items}}", "maxIterations": 10}, {}),
    "agentNode": (
        {
            "name": "Agent",
            "providerId": REF,
            "fallbackChainId": OTHER_REF,
            "compactingModel": REF,
            "systemPrompt": "Help with orders",
            "memoryTrimmingMode": "token_budget",
            "tokenBudget": 4000,
            "conversationHistoryTokens": 2000,
            "ragVectorConfig": {"vector_db_type": "chroma", "embedding_api_key": "sk-live-1"},
        },
        {
            "providerId": None,
            "fallbackChainId": None,
            "compactingModel": None,
            "ragVectorConfig": {"vector_db_type": "chroma"},
        },
    ),
    "subAgentNode": (
        {"name": "Helper", "providerId": REF, "fallbackChainId": REF, "compactingModel": REF, "mode": "task"},
        {"providerId": None, "fallbackChainId": None, "compactingModel": None},
    ),
    "llmModelNode": (
        {"name": "LLM", "providerId": REF, "fallbackChainId": REF, "compactingModel": REF, "userPrompt": "{{x}}"},
        {"providerId": None, "fallbackChainId": None, "compactingModel": None},
    ),
    "apiToolNode": (
        {
            "name": "API",
            "endpoint": "https://api.example.com/orders",
            "method": "GET",
            "headers": {"Authorization": "Bearer at-1"},
            "parameters": {"q": "{{input.q}}", "api_key": "sk-live-1", "token": "{{input.token}}"},
            "requestBody": "{}",
        },
        {"headers": GONE, "parameters": {"q": "{{input.q}}", "token": "{{input.token}}"}},
    ),
    "openApiNode": (
        {
            "name": "Spec",
            "providerId": REF,
            "query": "{{input.message}}",
            "originalFileName": "spec.yaml",
            "serverFilePath": "/data/tenants/acme/openapi/spec.yaml",
            "serverFileUrl": "https://files.example.com/spec.yaml",
        },
        {"providerId": None, "originalFileName": GONE, "serverFilePath": GONE, "serverFileUrl": GONE},
    ),
    "templateNode": ({"name": "Format", "template": "Hello {{input.name}}"}, {}),
    "knowledgeBaseNode": (
        {"name": "Docs", "selectedBases": [REF, OTHER_REF], "query": "{{input.message}}", "limit": 5},
        {"selectedBases": []},
    ),
    "pythonToolNode": ({"name": "Tool", "code": "result = 1"}, {}),
    "dataMapperNode": ({"name": "Map", "pythonScript": "result = params"}, {}),
    "toolBuilderNode": (
        {"name": "Lookup", "description": "Finds an order", "inputSchema": {"order_id": {"type": "string"}}},
        {},
    ),
    "slackMessageNode": (
        {"name": "Slack", "app_settings_id": REF, "channel": "#support", "message": "{{agent.output}}"},
        {"app_settings_id": None},
    ),
    "calendarEventNode": (
        {"name": "Calendar", "dataSourceId": REF, "operation": "create_calendar_event", "summary": "Call"},
        {"dataSourceId": None},
    ),
    "readMailsNode": (
        {"name": "Mail", "dataSourceId": REF, "searchCriteria": {"from": "billing@example.com", "max_results": 10}},
        {"dataSourceId": None},
    ),
    "gmailNode": (
        {
            "name": "Gmail",
            "dataSourceId": REF,
            "operation": "send_email",
            "to": "{{input.email}}",
            "subject": "Your order",
            "attachments": ["data:application/pdf;base64,JVBERi0xLjQK"],
        },
        {"dataSourceId": None, "attachments": GONE},
    ),
    "whatsappToolNode": (
        {"name": "WhatsApp", "app_settings_id": REF, "recipient_number": "{{input.phone}}", "message": "Hi"},
        {"app_settings_id": None},
    ),
    "zendeskTicketNode": (
        {"name": "Zendesk", "app_settings_id": REF, "subject": "Refund", "requester_email": "{{input.email}}"},
        {"app_settings_id": None},
    ),
    "salesforceCaseNode": (
        {
            "name": "Salesforce",
            "app_settings_id": REF,
            "subject": "Refund",
            "custom_fields": [{"key": "Region__c", "value": "EU"}, {"key": "Api_Key__c", "value": "k-1"}],
        },
        {
            "app_settings_id": None,
            "custom_fields": [{"key": "Region__c", "value": "EU"}, {"key": "Api_Key__c", "value": ""}],
        },
    ),
    "pythonCodeNode": ({"name": "Code", "code": "result = 1"}, {}),
    "sqlNode": (
        {
            "name": "SQL",
            "dataSourceId": REF,
            "providerId": REF,
            "mode": "sqlQuery",
            "sqlQuery": "SELECT * FROM orders WHERE region = :region",
            "parameters": {"region": "{{input.region}}", "db_password": "pw-1"},
        },
        {"dataSourceId": None, "providerId": None, "parameters": {"region": "{{input.region}}"}},
    ),
    "aggregatorNode": ({"name": "Join", "aggregationStrategy": "merge", "timeoutSeconds": 30}, {}),
    "jiraNode": (
        {
            "name": "Jira",
            "app_settings_id": REF,
            "spaceKey": "SUP",
            "taskName": "{{input.subject}}",
            "url": "https://acme.atlassian.net",
            "email": "admin@acme.example",
            "apiToken": "jira-token-1",
        },
        {"app_settings_id": None, "url": GONE, "email": GONE, "apiToken": GONE},
    ),
    "mlModelInferenceNode": (
        {"name": "Score", "modelId": REF, "modelName": "Churn model", "inferenceInputs": {"tenure": "{{x}}"}},
        {"modelId": None, "modelName": GONE},
    ),
    "trainDataSourceNode": (
        {
            "name": "Data",
            "sourceType": "csv",
            "dataSourceId": REF,
            "csvFileName": "customers.csv",
            "csvFilePath": "/data/tenants/acme/ml_training/customers.csv",
            "csvFileId": OTHER_REF,
            "csvFileUrl": "https://files.example.com/customers.csv",
            "sheetName": "Sheet1",
            "analysisResult": SAMPLE_ROWS,
        },
        {
            "dataSourceId": None,
            "csvFileName": GONE,
            "csvFilePath": GONE,
            "csvFileId": GONE,
            "csvFileUrl": GONE,
            "analysisResult": GONE,
        },
    ),
    "threadRAGNode": (
        {
            "name": "Memory",
            "action": "retrieve",
            "query": "{{input.message}}",
            "ragVectorConfig": {"embedding_type": "openai", "openai_api_key": "sk-live-1", "chunk_size": 500},
        },
        {"ragVectorConfig": {"embedding_type": "openai", "chunk_size": 500}},
    ),
    "preprocessingNode": (
        {
            "name": "Prep",
            "fileUrl": "{{source.data_path}}",
            "pythonCode": "df = df.dropna()",
            "analysisResult": SAMPLE_ROWS,
            "stepAnalysisResults": {"initial": SAMPLE_ROWS},
            "analyzedFileUrl": "https://files.example.com/customers.csv",
        },
        {"analysisResult": GONE, "stepAnalysisResults": GONE, "analyzedFileUrl": GONE},
    ),
    "trainModelNode": (
        {
            "name": "Train",
            "fileUrl": "/data/tenants/acme/ml_training/clean.csv",
            "analysisResult": SAMPLE_ROWS,
            "modelType": "xgboost",
            "targetColumn": "churn",
            "featureColumns": ["tenure"],
            "validationSplit": 0.2,
        },
        {"fileUrl": GONE, "analysisResult": GONE},
    ),
    "mcpNode": (
        {
            "name": "MCP",
            "description": "Order tools",
            "connectionType": "http",
            "connectionConfig": {"url": "https://mcp.example.com", "api_key": "k-1"},
            "availableTools": [{"name": "get_order", "description": "Reads an order"}],
            "whitelistedTools": ["get_order"],
        },
        {"connectionConfig": GONE, "availableTools": GONE, "whitelistedTools": GONE},
    ),
    "workflowExecutorNode": (
        {
            "name": "Run",
            "workflowId": REF,
            "workflowName": "Refunds",
            "inputParameters": {"order": "{{input.order}}", "access_token": "at-1"},
        },
        {"workflowId": None, "workflowName": GONE, "inputParameters": {"order": "{{input.order}}"}},
    ),
    "humanInTheLoopNode": (
        {"name": "Ask", "message": "Confirm the refund", "form_fields": [{"name": "approved", "type": "boolean"}]},
        {},
    ),
    "setStateNode": (
        {
            "name": "State",
            "states": [
                {"key": "tier", "value": "gold"},
                {"key": "api_token", "value": "at-1"},
                {"key": "password", "value": "{{input.password}}"},
            ],
        },
        {
            "states": [
                {"key": "tier", "value": "gold"},
                {"key": "api_token", "value": ""},
                {"key": "password", "value": "{{input.password}}"},
            ]
        },
    ),
    "guardrailProvenanceNode": (
        {"name": "Grounded", "provenance_mode": "llm", "llm_provider_id": REF, "min_score": 0.5},
        {"llm_provider_id": None},
    ),
    "guardrailNliNode": ({"name": "NLI", "nli_model_name": "cross-encoder/nli", "min_entail_score": 0.5}, {}),
    "fileReaderNode": (
        {
            "name": "Policy",
            "fileSource": "upload",
            "fileName": "policy.pdf",
            "filePath": "/data/tenants/acme/uploads/policy.pdf",
            "fileUrl": "https://files.example.com/policy.pdf",
            "fileId": REF,
        },
        {"fileName": GONE, "filePath": GONE, "fileUrl": GONE, "fileId": GONE},
    ),
    "externalAgentNode": (
        {
            "name": "Partner",
            "endpoint": "https://agent.example.com",
            "authType": "bearer",
            "authToken": "at-1",
            "headers": {"X-Api-Key": "k-1"},
            "messageField": "reply",
        },
        {"authToken": GONE, "headers": GONE},
    ),
    "ttsNode": (
        {"name": "Speak", "text": "{{agent.output}}", "audioProviderId": REF, "voice": "alloy", "model": "tts-1"},
        {"audioProviderId": None},
    ),
    "sttNode": (
        {"name": "Listen", "audio_source": "{{input.audio}}", "audioProviderId": REF, "model": "whisper-1"},
        {"audioProviderId": None},
    ),
    "voiceAgentNode": (
        {"name": "Voice", "voiceProviderId": REF, "systemPrompt": "Be brief", "maxOutputTokens": 512},
        {"voiceProviderId": None},
    ),
    "createWorkflowScheduleNode": (
        {
            "name": "Daily",
            "agentId": REF,
            "cronSchedule": "0 9 * * *",
            "threadIdMode": "fixed",
            "fixedThreadId": OTHER_REF,
            "message": "Send the daily report",
        },
        {"agentId": None, "fixedThreadId": None},
    ),
    "webScraperNode": (
        {"name": "Scrape", "url": "https://example.com", "format": "markdown", "headers": '{"Cookie": "s=1"}'},
        {"headers": GONE},
    ),
    "webSearchNode": ({"name": "Search", "query": "{{input.message}}", "maxResults": 5}, {}),
    "htmlToImageNode": ({"name": "Render", "html": "<p>Hi</p>", "captureMode": "fullPage"}, {}),
    "nlpNode": (
        {"name": "Classify", "providerId": REF, "task": "classify", "categories": ["billing"]},
        {"providerId": None},
    ),
}


def test_every_block_type_has_a_cleaning_case():
    from app.api.v1.routes.workflows import SUPPORTED_NODE_TYPES

    assert set(BLOCKS) == set(SUPPORTED_NODE_TYPES)


@pytest.mark.parametrize("node_type", sorted(BLOCKS))
def test_cleaning_each_block_type(node_type):
    data, changes = BLOCKS[node_type]
    (node,), _ = sanitize_graph([{"id": "n1", "type": node_type, "data": data}], [])
    expected = {key: value for key, value in {**data, **changes}.items() if value is not GONE}
    assert node["data"] == expected


# Pickers that load their options at run time but don't point at a saved row.
NOT_CONNECTIONS = {
    "type",
    "method",
    "operation",
    "action",
    "compare_condition",
    "aggregationStrategy",
    "modelType",
    "categories",
    "tags",
    "labels",
    "featureColumns",
    "compactingImportantEntities",
    "searchCriteria.label",
    "searchCriteria.newer_than",
    "searchCriteria.older_than",
}


def test_every_runtime_picker_in_a_block_form_is_a_known_connection():
    from app.schemas.dynamic_form_schemas.nodes import NODE_DIALOG_SCHEMAS

    pickers = {
        field.name
        for fields in NODE_DIALOG_SCHEMAS.values()
        for field in fields
        if field.type in ("select", "tags") and not field.options
    }
    unknown = pickers - NOT_CONNECTIONS - set(PER_TENANT_REF_FIELDS)
    assert not unknown, f"Clean these in template_sanitizer.py or list them in NOT_CONNECTIONS: {sorted(unknown)}"


def test_cleaner_knows_every_connection_the_builder_knows():
    # The CI image has no frontend source; the form test above runs there instead.
    frontend = Path(__file__).resolve().parents[3] / "frontend"
    if not frontend.is_dir():
        pytest.skip("needs the frontend source next to the backend")
    references = frontend / "src/views/AIAgents/Workflows/utils/workflowReferences.ts"
    source = references.read_text(encoding="utf-8")
    keys = set(re.findall(r'\bkey: "(\w+)"', source))
    assert "providerId" in keys
    assert keys <= set(PER_TENANT_REF_FIELDS)
    # A copy of the target's name goes with its connection.
    name_keys = set(re.findall(r'\bnameKey: "(\w+)"', source))
    assert "modelName" in name_keys
    assert name_keys <= {field for fields in PUBLISHER_ONLY_FIELDS.values() for field in fields}


def test_variables_in_connections_and_files_are_kept():
    data = {"workflowId": "{{input.workflow}}", "fileUrl": "{{source.data_path}}"}
    (node,), _ = sanitize_graph([{"id": "n1", "type": "workflowExecutorNode", "data": data}], [])
    assert node["data"] == data


def test_secret_names_are_removed_at_any_depth():
    data = {
        "config": {
            "steps": [{"name": "fetch", "auth": {"client_secret": "s-1", "scope": "read"}}],
            "Proxy-Authorization": "Basic abc",
            "max_tokens": 256,
            "tokenizer": "cl100k",
        }
    }
    (node,), _ = sanitize_graph([{"id": "n1", "type": "futureNode", "data": data}], [])
    assert node["data"] == {
        "config": {
            "steps": [{"name": "fetch", "auth": {"scope": "read"}}],
            "max_tokens": 256,
            "tokenizer": "cl100k",
        }
    }


def test_secret_names_keep_a_value_that_is_only_a_variable():
    data = {
        "auth": {
            "token": "{{input.token}}",
            "api_key": " {{input.key}} ",
            "password": "pw {{input.suffix}}",
            # The engine reads spaces inside the braces as plain text, not a variable.
            "secret": "{{ input.secret }}",
        }
    }
    (node,), _ = sanitize_graph([{"id": "n1", "type": "futureNode", "data": data}], [])
    assert node["data"] == {"auth": {"token": "{{input.token}}", "api_key": " {{input.key}} "}}


def test_plural_token_names_are_secrets_but_token_counts_are_kept():
    counts = {
        "maxOutputTokens": 512,
        "max_tokens": 256,
        "conversationHistoryTokens": 2000,
        "tokenBudget": 4000,
        "token_limit": 10,
    }
    secrets = {
        "apiTokens": ["t-1"],
        "refresh_tokens": "r-1",
        "accessTokens": "a-1",
        "admin_tokens": "d-1",
        "tokens": "x-1",
        "contextToken": "c-1",
        "input_token": "i-1",
    }
    (node,), _ = sanitize_graph([{"id": "n1", "type": "futureNode", "data": {**counts, **secrets}}], [])
    assert node["data"] == counts


def test_other_credential_names_are_removed():
    secrets = {"auth": "Basic abc", "sshPassphrase": "p-1", "bearer": "b-1", "db_pwd": "p-2", "jwt": "j-1"}
    kept = {"authType": "basic", "authorUrl": "https://example.com/about"}
    (node,), _ = sanitize_graph([{"id": "n1", "type": "futureNode", "data": {**secrets, **kept}}], [])
    assert node["data"] == kept


def test_secret_named_field_mappings_lose_their_default():
    data = {
        "fieldMappings": [
            {"key": "api_token", "path": "headers.x-token", "default": "tok-1"},
            {"key": "order", "path": "body.order", "default": "none"},
        ]
    }
    (node,), _ = sanitize_graph([{"id": "n1", "type": "webhookTriggerNode", "data": data}], [])
    assert node["data"]["fieldMappings"] == [
        {"key": "api_token", "path": "headers.x-token"},
        {"key": "order", "path": "body.order", "default": "none"},
    ]


def test_variables_in_attachments_and_publisher_fields_are_kept():
    nodes = [
        {"id": "n1", "type": "gmailNode", "data": {"attachments": ["{{input.file}}", "/files/acme/report.pdf"]}},
        {"id": "n2", "type": "jiraNode", "data": {"url": "{{input.jira_url}}", "email": "ops@example.com"}},
    ]
    (gmail, jira), _ = sanitize_graph(nodes, [])
    assert gmail["data"] == {"attachments": ["{{input.file}}"]}
    assert jira["data"] == {"url": "{{input.jira_url}}"}


def test_values_that_only_contain_a_variable_are_cleaned():
    data = {
        "workflowId": "wf-{{input.n}}",
        "fileUrl": "https://files.example.com/acme/{{input.name}}?signature=abc",
        "filePath": "/data/acme/{{input.name}}.pdf",
    }
    (node,), _ = sanitize_graph([{"id": "n1", "type": "workflowExecutorNode", "data": data}], [])
    assert node["data"] == {"workflowId": None}


def test_edges_lose_secret_names():
    edge = {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "out", "data": {"api_key": "sk-1", "label": "yes"}}
    _, (clean,) = sanitize_graph([], [edge])
    assert clean == {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "out", "data": {"label": "yes"}}


def test_list_entries_named_like_secrets_lose_their_value():
    data = {
        "name": "Token check",
        "value": "gold",
        "rows": [
            {"name": "Authorization", "value": "Bearer abc"},
            {"header": "X-Api-Key", "value": "k-1"},
            {"name": "Accept", "value": "application/json"},
        ],
    }
    (node,), _ = sanitize_graph([{"id": "n1", "type": "filterNode", "data": data}], [])
    # Only list entries count: a block's own name and value stay as they are.
    assert node["data"] == {
        "name": "Token check",
        "value": "gold",
        "rows": [
            {"name": "Authorization", "value": ""},
            {"header": "X-Api-Key", "value": ""},
            {"name": "Accept", "value": "application/json"},
        ],
    }


def test_sanitize_test_input_cleans_nested_values():
    safe = sanitize_test_input([], {"message": "hi", "metadata": {"api_key": "sk-1", "plan": "pro"}})
    assert safe == {"message": "hi", "metadata": {"plan": "pro"}}


def test_sanitize_template_graph_cleans_nodes_and_sample_input():
    nodes, edges = _graph()
    graph = sanitize_template_graph({"nodes": nodes, "edges": edges, "testInput": {"apiKey": "sk-1"}})
    assert graph == {"nodes": sanitize_graph(nodes, edges)[0], "edges": edges}
    assert sanitize_template_graph(None) == {"nodes": [], "edges": []}
