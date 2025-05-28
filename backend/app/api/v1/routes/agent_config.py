from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Body, Depends

from app.auth.dependencies import auth
from app.modules.agents.llm.provider import LLMProvider
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.services.agent_config import AgentConfigService


router = APIRouter()

# TODO set permission validation
@router.get("/configs", response_model=List[AgentRead], dependencies=[
    Depends(auth),
    ])
async def get_all_configs(
        config_service: AgentConfigService = Depends()
):
    """Get all agent configurations"""
    models = await config_service.get_all_full()
    agent_reads = [
        AgentRead(**agent_model.__dict__).model_copy(update={
            "user_id": agent_model.operator.user.id
            })
        for agent_model in models
        ]
    return agent_reads


@router.get("/configs/{agent_id}", response_model=AgentRead, dependencies=[
    Depends(auth),
    ])
async def get_config_by_id(
        agent_id: UUID,
        config_service: AgentConfigService = Depends()
):
    """Get a specific agent configuration by ID"""
    agent_model = await config_service.get_by_id_full(agent_id)
    agent_read = AgentRead(**agent_model.__dict__).model_copy(update={
            "user_id": agent_model.operator.user.id
            })
    agent_read.user_id = agent_model.operator.user.id
    return agent_read

@router.post("/configs", response_model=AgentRead, dependencies=[
    Depends(auth),
    ])
async def create_config(
        agent_create: AgentCreate = Body(...),
        config_service: AgentConfigService = Depends()
):
    """Create a new agent configuration"""
    result = await config_service.create(agent_create)

    return AgentRead(
            **result.__dict__,
            )


@router.put("/configs/{agent_id}", response_model=AgentRead, dependencies=[
    Depends(auth),
    ])
async def update_config(
        agent_id: UUID,
        agent_update: AgentUpdate = Body(...),
        agent_config_service: AgentConfigService = Depends()
):
    """Update an existing agent configuration"""

    result = await agent_config_service.update(agent_id, agent_update)
    return AgentRead(
            **result.__dict__,
            )


@router.delete("/configs/{agent_id}", response_model=Dict[str, str], dependencies=[
    Depends(auth),
    ])
async def delete_config(
        agent_id: UUID,
        config_service: AgentConfigService = Depends()
):
    """Delete an agent configuration"""
    await config_service.delete(agent_id)
    return {"status": "success", "message": f"Configuration with ID {agent_id} deleted"}


@router.get("/supported_models", dependencies=[
    Depends(auth),
])
async def get_supported_models():
    return LLMProvider.get_instance().get_configuration_definitions()
