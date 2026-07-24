"""Unit tests for the Template Marketplace graph sanitizer."""
from app.services.template_sanitizer import sanitize_graph, sanitize_test_input


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
