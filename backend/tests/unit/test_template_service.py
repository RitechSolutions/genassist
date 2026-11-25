"""Unit tests for the Template Marketplace service."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.utils.enums.template_status_enum import TemplateStatus
from app.schemas.template import TemplateRead
from app.services.template import TemplateService


@pytest.mark.asyncio
async def test_opening_a_template_cleans_rows_stored_under_older_rules():
    user_id = uuid4()
    slack = {"name": "Slack", "app_settings_id": str(uuid4()), "channel": "#support"}
    row = SimpleNamespace(
        id=uuid4(),
        title="Support",
        graph={"nodes": [{"id": "n1", "type": "slackMessageNode", "data": slack}], "edges": []},
        is_deleted=False,
        created_by=user_id,
        status=TemplateStatus.APPROVED,
    )
    master = AsyncMock()
    master.get_by_id.return_value = None
    repository = AsyncMock()
    repository.get_by_id.return_value = row
    service = TemplateService(repository=repository, workflow_service=AsyncMock(), agent_config_service=AsyncMock())

    @asynccontextmanager
    async def master_repo():
        yield master

    service._master_repo = master_repo

    own = await service.get_template(row.id, user_id)
    master.get_by_id.return_value = row
    shared = await service.get_template(row.id, uuid4())

    for read in (own, shared):
        assert read.graph["nodes"][0]["data"] == {"name": "Slack", "app_settings_id": None, "channel": "#support"}
    assert shared.is_global


@pytest.mark.asyncio
async def test_install_cleans_the_graph_and_the_sample_input():
    workflow_service = AsyncMock()
    workflow_service.create.return_value = SimpleNamespace(id=uuid4())
    agent_config_service = AsyncMock()
    agent_config_service.create.return_value = SimpleNamespace(id=uuid4())
    service = TemplateService(
        repository=AsyncMock(),
        workflow_service=workflow_service,
        agent_config_service=agent_config_service,
    )
    # A copy stored before cleaning covered connections and sample input values.
    service.get_template = AsyncMock(
        return_value=TemplateRead(
            id=uuid4(),
            title="Support",
            graph={
                "nodes": [
                    {
                        "id": "n1",
                        "type": "chatInputNode",
                        "data": {
                            "inputSchema": {
                                "message": {"type": "string"},
                                "plan": {"type": "string", "hidden": True},
                            }
                        },
                    },
                    {
                        "id": "n2",
                        "type": "slackMessageNode",
                        "data": {"name": "Slack", "app_settings_id": str(uuid4()), "channel": "#support"},
                    },
                ],
                "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
                "testInput": {"message": "hi", "plan": "gold", "metadata": {"api_key": "sk-1", "region": "eu"}},
            },
        )
    )

    await service.install(uuid4(), None, uuid4())

    created = workflow_service.create.call_args.args[0]
    slack = next(node for node in created.nodes if node["id"] == "n2")
    assert slack["data"] == {"name": "Slack", "app_settings_id": None, "channel": "#support"}
    assert created.testInput == {"message": "hi", "metadata": {"region": "eu"}}
