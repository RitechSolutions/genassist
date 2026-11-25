"""Creating an agent links its workflow back to it without erasing workflow fields."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.agent import AgentCreate
from app.services import agent_config
from app.services.agent_config import AgentConfigService


@pytest.mark.asyncio
async def test_create_keeps_the_workflow_sample_input_and_settings(monkeypatch):
    workflow = SimpleNamespace(
        id=uuid4(),
        name="Support",
        description=None,
        nodes=[{"id": "n1", "type": "chatInputNode", "data": {}}],
        edges=[],
        testInput={"message": "hi"},
        executionState=None,
        settings={"nodeStyle": "compact"},
        version="1.0",
    )
    workflow_service = MagicMock()
    workflow_service.get_by_id = AsyncMock(return_value=workflow)
    workflow_service.update = AsyncMock()
    repository = MagicMock()
    repository.create = AsyncMock(return_value=SimpleNamespace(id=uuid4(), workflow_id=workflow.id))
    operator_service = MagicMock()
    operator_service.create_from_agent = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    db = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    monkeypatch.setattr(agent_config, "null_unloaded_attributes", lambda obj: None)
    service = AgentConfigService(
        repository=repository,
        operator_service=operator_service,
        workflow_service=workflow_service,
        user_types_repository=MagicMock(),
        db=db,
    )

    await service.create(
        AgentCreate(
            name="Support",
            description="Answers questions",
            welcome_message="Hi",
            possible_queries=[],
            workflow_id=workflow.id,
        ),
        user_id=uuid4(),
    )

    update = workflow_service.update.call_args.args[1]
    assert update.testInput == {"message": "hi"}
    assert update.settings == {"nodeStyle": "compact"}
    assert update.nodes == workflow.nodes
