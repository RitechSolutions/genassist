"""Workflow Builder review findings: simulated test runs, secrets in the draft status, draft
ownership, and the legacy wizard endpoint"""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import workflow_builder as routes
from app.api.v1.routes import workflow_manager as manager_routes
from app.modules.workflow.builder import catalog, testing
from app.modules.workflow.builder.assist import ACTION_NODE_TYPES
from app.modules.workflow.builder.draft import WorkflowDraft


def _request(user_id=None):
    user = SimpleNamespace(id=user_id) if user_id else None
    return SimpleNamespace(state=SimpleNamespace(user=user), base_url="http://test/")


class _Store:
    """In-memory stand-in for the conversation-memory draft storage"""

    def __init__(self):
        self.drafts = {}

    async def load(self, thread_id):
        payload = self.drafts.get(str(thread_id))
        return WorkflowDraft.from_dict(json.loads(payload)) if payload else None

    async def save(self, thread_id, draft):
        self.drafts[str(thread_id)] = json.dumps(draft.to_dict())


@pytest.fixture
def store(monkeypatch):
    s = _Store()
    monkeypatch.setattr(routes, "load_draft", s.load)
    monkeypatch.setattr(routes, "save_draft", s.save)
    return s


class _NoDefaultProvider:
    async def get_default(self):
        raise LookupError("none")


def _canvas():
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("chatOutputNode", "Reply", connect_from="n1")
    return draft.to_canvas()


# ── 2: simulated test runs bypass every step that reaches outside ─────────


SIDE_EFFECT_NODES = (
    "sqlNode", "apiToolNode", "openApiNode", "mcpNode", "createWorkflowScheduleNode", "workflowExecutorNode",
)


def test_the_simulated_set_covers_sql_api_openapi_mcp_schedules_and_sub_workflows():
    assert set(SIDE_EFFECT_NODES) <= ACTION_NODE_TYPES
    assert all(catalog.is_known(t) for t in ACTION_NODE_TYPES), "a renamed node type would silently stop being simulated"


@pytest.mark.parametrize("node_type", SIDE_EFFECT_NODES)
def test_a_simulated_builder_test_run_never_executes_a_side_effect_step(monkeypatch, node_type):
    executed = {}

    class FakeEngine:
        def __init__(self, workflow):
            executed["nodes"] = workflow["nodes"]

        async def execute_from_node(self, input_data, thread_id, persist, usage_sink):
            return SimpleNamespace(format_state_as_response=lambda: {
                "output": {"message": "ok"}, "failed_nodes": [], "state": {"nodeExecutionStatus": {}},
            })

    import app.modules.workflow.engine.workflow_engine as engine_module

    monkeypatch.setattr(engine_module, "WorkflowEngine", FakeEngine)
    monkeypatch.setattr(testing, "blocking", lambda issues: [])  # setup fields are not the point here

    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    # Unconnected: some of these are tool nodes (MCP) without an input; the engine is a stub anyway.
    draft.add_node(node_type, "Side effect")
    draft.add_node("chatOutputNode", "Reply", connect_from="n1")

    report = asyncio.run(testing.run_draft_test(draft, "hello"))

    step = next(n for n in executed["nodes"] if n["type"] == node_type)
    assert step["data"]["deactivated"] is True
    assert 'Simulated (nothing was really sent or created): n2 "Side effect"' in report
    assert not draft.find("n2")["data"].get("deactivated")  # the draft itself is untouched

    draft.simulate_actions = False
    asyncio.run(testing.run_draft_test(draft, "hello"))
    step = next(n for n in executed["nodes"] if n["type"] == node_type)
    assert not step["data"].get("deactivated")


# ── 3: the status endpoint never returns credentials ──────────────────────


def test_redact_secrets_removes_credentials_at_any_depth_and_keeps_settings():
    config = {
        "authToken": "tok-123",
        "authPassword": "hunter2",
        "authHeader": "Authorization",
        "authType": "bearer",
        "endpoint": "https://api.example.com",
        "headers": {"Authorization": "Bearer abc", "X-Api-Key": "k", "Content-Type": "application/json"},
        "connectionConfig": {"url": "https://mcp", "headers": [{"key": "Cookie", "value": "s=1"}, {"key": "Accept", "value": "x"}]},
        "max_tokens": 4000,
        "apiToken": "",
    }
    redacted = catalog.redact_secrets(config)

    text = json.dumps(redacted)
    for secret in ("tok-123", "hunter2", "Bearer abc", '"k"', "s=1"):
        assert secret not in text
    assert redacted["authHeader"] == "Authorization" and redacted["authType"] == "bearer"
    assert redacted["headers"] == {"Content-Type": "application/json"}
    assert redacted["connectionConfig"]["headers"] == [{"key": "Cookie"}, {"key": "Accept", "value": "x"}]
    assert redacted["max_tokens"] == 4000 and redacted["endpoint"] == "https://api.example.com"
    assert config["authToken"] == "tok-123", "the draft itself is not changed"


def test_the_draft_status_spec_carries_no_credentials(store):
    conversation_id = uuid4()
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node(
        "externalAgentNode", "Partner",
        {"endpoint": "https://partner.example", "authType": "bearer", "authToken": "tok-secret",
         "headers": {"Authorization": "Bearer also-secret"}},
        connect_from="n1",
    )
    draft.add_node("chatOutputNode", "Reply", connect_from="n2")
    asyncio.run(store.save(conversation_id, draft))

    status = asyncio.run(routes.get_draft_status(conversation_id, _request()))

    text = json.dumps(status)
    assert "tok-secret" not in text and "also-secret" not in text
    partner = next(n for n in status["spec"]["workflow"] if n["node_name"] == "externalAgentNode")
    assert partner["config"]["endpoint"] == "https://partner.example"
    # The stored draft keeps the credential; only the preview drops it.
    assert "tok-secret" in store.drafts[str(conversation_id)]


# ── 4: a draft opened from a canvas belongs to its user ───────────────────


def test_put_draft_records_the_owner_and_refuses_another_user(store):
    owner, other = uuid4(), uuid4()
    conversation_id = uuid4()
    snapshot = routes.CanvasSnapshot(**_canvas())

    asyncio.run(routes.put_draft(conversation_id, snapshot, _request(owner), _NoDefaultProvider()))
    assert json.loads(store.drafts[str(conversation_id)])["owner_id"] == str(owner)

    with pytest.raises(HTTPException) as refused:
        asyncio.run(routes.put_draft(conversation_id, snapshot, _request(other), _NoDefaultProvider()))
    assert refused.value.status_code == 403
    assert json.loads(store.drafts[str(conversation_id)])["owner_id"] == str(owner), "nothing was overwritten"

    # Its owner can keep replacing it.
    asyncio.run(routes.put_draft(conversation_id, snapshot, _request(owner), _NoDefaultProvider()))


def test_someone_elses_draft_reads_as_missing_everywhere(store):
    owner, other = uuid4(), uuid4()
    conversation_id = uuid4()
    asyncio.run(routes.put_draft(conversation_id, routes.CanvasSnapshot(**_canvas()), _request(owner), _NoDefaultProvider()))

    assert asyncio.run(routes.get_draft(conversation_id, _request(owner)))["nodes"]
    with pytest.raises(HTTPException) as missing:
        asyncio.run(routes.get_draft(conversation_id, _request(other)))
    assert missing.value.status_code == 404

    # The chat API key (no user) and other users see no draft through the status endpoint.
    for caller in (_request(), _request(other)):
        status = asyncio.run(routes.get_draft_status(conversation_id, caller))
        assert status["status"] == "empty" and status["spec"] is None
    assert asyncio.run(routes.get_draft_status(conversation_id, _request(owner)))["node_count"] == 2

    with pytest.raises(HTTPException) as not_created:
        asyncio.run(routes.create_workflow_from_builder(
            request=_request(other), workflow_name="x", workflow_json=None, workflow_description="",
            conversation_id=conversation_id, dry_run=True, agent_service=None, workflow_service=None,
            llm_provider_service=_NoDefaultProvider(),
        ))
    assert not_created.value.status_code == 404


def test_an_onboarding_draft_without_an_owner_stays_usable(store):
    """The pre-login chat starts a draft before any user exists; it is created after login."""
    conversation_id = uuid4()
    draft = WorkflowDraft()
    draft.add_node("chatInputNode", "Start")
    draft.add_node("chatOutputNode", "Reply", connect_from="n1")
    asyncio.run(store.save(conversation_id, draft))

    assert asyncio.run(routes.get_draft_status(conversation_id, _request()))["node_count"] == 2
    assert asyncio.run(routes.get_draft_status(conversation_id, _request(uuid4())))["node_count"] == 2


def test_the_owner_survives_the_agents_own_saves():
    draft = WorkflowDraft()
    draft.owner_id = "user-1"
    assert WorkflowDraft.from_dict(json.loads(json.dumps(draft.to_dict()))).owner_id == "user-1"
    assert WorkflowDraft.from_dict({}).owner_id is None


# ── 8: the legacy wizard endpoint keeps accepting what it used to ─────────


class _AgentService:
    def __init__(self):
        self.deleted = []

    async def create(self, agent_create, user_id=None):
        self.created = agent_create
        return SimpleNamespace(id=uuid4(), workflow_id=uuid4())

    async def delete(self, agent_id):
        self.deleted.append(agent_id)


class _WorkflowService:
    async def get_by_id(self, workflow_id):
        record = SimpleNamespace(
            id=workflow_id, name="w", description="d", user_id=None, agent_id=uuid4(),
            nodes=[], edges=[], executionState={}, testInput={},
        )
        record.model_dump = lambda: {"nodes": record.nodes, "edges": record.edges}
        return record

    async def update(self, workflow_id, data):
        self.saved = data


def test_wizard_json_the_validated_build_rejects_is_still_created_the_legacy_way(monkeypatch):
    async def strict_build(**kwargs):
        raise HTTPException(status_code=400, detail={"message": "The workflow specification is not valid"})

    monkeypatch.setattr(manager_routes, "create_workflow_from_builder", strict_build)
    wizard_json = json.dumps({"workflow": [
        {"uniqueId": "1", "node_name": "chatInputNode", "function_of_node": "Start"},
        {"uniqueId": "2", "node_name": "agentNode", "function_of_node": "Answer", "config": {"notAField": 1}},
    ]})
    workflows = _WorkflowService()

    result = asyncio.run(manager_routes.create_workflow_from_wizard(
        request=_request(uuid4()), workflow_name="Legacy", workflow_json=wizard_json,
        agent_service=_AgentService(), workflow_service=workflows, llm_provider_service=None,
    ))

    assert [n["type"] for n in workflows.saved.nodes] == ["chatInputNode", "agentNode"]
    assert workflows.saved.edges == []
    assert result["worflow_json"] == result["workflow_json"] == wizard_json


def test_the_wizard_response_keeps_its_original_key_on_the_validated_path(monkeypatch):
    async def build(**kwargs):
        return {"id": "w1", "agent_id": "a1"}

    monkeypatch.setattr(manager_routes, "create_workflow_from_builder", build)
    result = asyncio.run(manager_routes.create_workflow_from_wizard(
        request=_request(), workflow_name="n", workflow_json='{"workflow": []}',
        agent_service=None, workflow_service=None, llm_provider_service=None,
    ))
    assert result["worflow_json"] == '{"workflow": []}'


@pytest.mark.parametrize("bad", ["not json", "[]", '{"nodes": []}'])
def test_input_that_is_not_wizard_json_keeps_its_400(monkeypatch, bad):
    async def strict_build(**kwargs):
        raise HTTPException(status_code=400, detail="invalid")

    monkeypatch.setattr(manager_routes, "create_workflow_from_builder", strict_build)
    agents = _AgentService()
    with pytest.raises(HTTPException) as refused:
        asyncio.run(manager_routes.create_workflow_from_wizard(
            request=_request(), workflow_name="n", workflow_json=bad,
            agent_service=agents, workflow_service=None, llm_provider_service=None,
        ))
    assert refused.value.status_code == 400
    assert not hasattr(agents, "created"), "nothing was created"
