<<<<<<< HEAD
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List, Dict

from app.services.agent_config import AgentConfigService
from app.schemas.agent_config import AgentConfig
from app.dependencies.agents import get_agent_config_service

router = APIRouter()

@router.get("/configs", response_model=List[AgentConfig])
async def get_all_configs(
    config_service: AgentConfigService = Depends(get_agent_config_service)
):
    """Get all agent configurations"""
    configs = await config_service.get_all()
    return configs

@router.get("/configs/{config_id}", response_model=AgentConfig)
async def get_config_by_id(
    config_id: str,
    config_service: AgentConfigService = Depends(get_agent_config_service)
):
    """Get a specific agent configuration by ID"""
    config = await config_service.get_by_id(config_id)
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration with ID {config_id} not found")
    return config

@router.post("/configs", response_model=AgentConfig)
async def create_config(
    config: AgentConfig = Body(...),
    config_service: AgentConfigService = Depends(get_agent_config_service)
):
    """Create a new agent configuration"""

    # Check if config with this ID already exists
    existing = await config_service.get_by_id(config.id)

    if existing:
        raise HTTPException(status_code=400, detail=f"Configuration with ID {config.id} already exists")
    
    result = await config_service.create(config)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create configuration")
    
    return result

@router.put("/configs/{config_id}", response_model=AgentConfig)
async def update_config(
    config_id: str,
    config: AgentConfig = Body(...),
    config_service: AgentConfigService = Depends(get_agent_config_service)
):
    """Update an existing agent configuration"""
    # Check if config exists
    existing = await config_service.get_by_id(config_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Configuration with ID {config_id} not found")
    
    # Ensure the ID in the path matches the ID in the body
    if config.id != config_id:
        raise HTTPException(status_code=400, detail="ID in path must match ID in body")
    
    result = await config_service.update(config_id, config)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update configuration")
    
    return result

@router.delete("/configs/{config_id}", response_model= Dict[str, str])
async def delete_config(
    config_id: str,
    config_service: AgentConfigService = Depends(get_agent_config_service)
):
    """Delete an agent configuration"""
    # Check if config exists
    existing = await config_service.get_by_id(config_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Configuration with ID {config_id} not found")
    
    result = await config_service.delete(config_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to delete configuration")
    
    return {"status": "success", "message": f"Configuration with ID {config_id} deleted"}
=======
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
>>>>>>> development
