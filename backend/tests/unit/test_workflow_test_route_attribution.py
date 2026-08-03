"""The Agent Studio workflow-test route runs the submitted graph unchanged while
attributing its LLM usage to the saved workflow it came from"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.api.v1.routes.workflows as workflows_route


class FakeEngine:

    last: "FakeEngine | None" = None

    def __init__(self, workflow_config):
        self.workflow_config = workflow_config
        self.workflow_id = workflow_config.get("id")
        self.execute_kwargs = None
        FakeEngine.last = self

    async def execute_from_node(self, **kwargs):
        self.execute_kwargs = kwargs
        return SimpleNamespace(format_state_as_response=lambda: {"status": "completed"})


class FakeTurnRouter:
    def __init__(self, engine, owner_id):
        self.owner_id = owner_id

    def has_sub_agents(self):
        return False

    def finalize(self, response):
        return response


class FakeWorkflowService:
    def __init__(self, workflow=None):
        self.workflow = workflow
        self.requested_id = None

    async def get_by_id(self, workflow_id):
        self.requested_id = workflow_id
        return self.workflow


@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch):
    monkeypatch.setattr(workflows_route, "WorkflowEngine", FakeEngine)
    monkeypatch.setattr(workflows_route, "SubAgentTurnRouter", FakeTurnRouter)
    FakeEngine.last = None


def _graph(**overrides) -> dict:
    graph = {"name": "Studio graph", "version": "1", "nodes": [], "edges": []}
    graph.update(overrides)
    return graph


@pytest.mark.asyncio
async def test_saved_graph_attributes_usage_without_changing_execution():
    saved_id = uuid4()
    await workflows_route.test_workflow(
        {"input_data": {"message": "hi"}, "workflow": _graph(id=str(saved_id))},
        workflow_service=FakeWorkflowService(),
    )

    engine = FakeEngine.last
    assert engine.workflow_config["id"] == "test-workflow"
    usage_context = engine.execute_kwargs["usage_context"]
    assert usage_context.source == "workflow_test"
    assert usage_context.workflow_id == saved_id
    assert usage_context.agent_id is None


@pytest.mark.asyncio
async def test_unsaved_graph_stays_unattributed():
    await workflows_route.test_workflow(
        {"input_data": {"message": "hi"}, "workflow": _graph()},
        workflow_service=FakeWorkflowService(),
    )

    engine = FakeEngine.last
    assert engine.workflow_config["id"] == "test-workflow"
    assert engine.execute_kwargs["usage_context"].workflow_id is None


@pytest.mark.asyncio
async def test_unparsable_submitted_id_stays_unattributed():
    await workflows_route.test_workflow(
        {"input_data": {"message": "hi"}, "workflow": _graph(id="not-a-uuid")},
        workflow_service=FakeWorkflowService(),
    )

    assert FakeEngine.last.execute_kwargs["usage_context"].workflow_id is None


@pytest.mark.asyncio
async def test_workflow_id_query_param_path_is_unchanged():
    saved_id = uuid4()
    service = FakeWorkflowService(SimpleNamespace(nodes=[], edges=[]))

    await workflows_route.test_workflow(
        {"input_data": {"message": "hi"}},
        workflow_id=saved_id,
        workflow_service=service,
    )

    engine = FakeEngine.last
    assert service.requested_id == saved_id
    assert engine.workflow_config["id"] == str(saved_id)
    assert engine.execute_kwargs["usage_context"].workflow_id == saved_id


@pytest.mark.asyncio
async def test_submitted_graph_and_run_inputs_reach_the_engine_verbatim():
    nodes = [{"id": "n1", "type": "chatInputNode"}]
    edges = [{"id": "e1", "source": "n1", "target": "n1"}]
    await workflows_route.test_workflow(
        {
            "input_data": {"message": "hi", "thread_id": "t-1", "human_in_the_loop_node_id": "n1"},
            "workflow": _graph(id=str(uuid4()), nodes=nodes, edges=edges),
        },
        workflow_service=FakeWorkflowService(),
    )

    engine = FakeEngine.last
    assert engine.workflow_config["nodes"] == nodes
    assert engine.workflow_config["edges"] == edges
    assert engine.execute_kwargs["thread_id"] == "t-1"
    assert engine.execute_kwargs["start_node_id"] == "n1"
    assert engine.execute_kwargs["registry_managed"] is True
