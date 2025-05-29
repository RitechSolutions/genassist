from fastapi import APIRouter, HTTPException, Query, Depends, Body
from typing import List, Dict, Any, Optional
import json
import os
from pydantic import BaseModel

from app.genagent.services.agent_config_service import AgentConfigService
from app.genagent.models.config import AgentConfig
from app.genagent.core.dependencies import get_config_service

router = APIRouter()

@router.get("/configs", response_model=List[AgentConfig])
async def get_all_configs(
    config_service: AgentConfigService = Depends(get_config_service)
):
    """Get all agent configurations"""
    configs = await config_service.get_all_configs()
    return configs

@router.get("/configs/{config_id}", response_model=AgentConfig)
async def get_config_by_id(
    config_id: str,
    config_service: AgentConfigService = Depends(get_config_service)
):
    """Get a specific agent configuration by ID"""
    config = await config_service.get_config_by_id(config_id)
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration with ID {config_id} not found")
    return config

@router.post("/configs", response_model=AgentConfig)
async def create_config(
    config: AgentConfig = Body(...),
    config_service: AgentConfigService = Depends(get_config_service)
):
    """Create a new agent configuration"""

    # Check if config with this ID already exists
    existing = await config_service.get_config_by_id(config.id)

    if existing:
        raise HTTPException(status_code=400, detail=f"Configuration with ID {config.id} already exists")
    
    result = await config_service.create_config(config)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create configuration")
    
    return result

@router.put("/configs/{config_id}", response_model=AgentConfig)
async def update_config(
    config_id: str,
    config: AgentConfig = Body(...),
    config_service: AgentConfigService = Depends(get_config_service)
):
    """Update an existing agent configuration"""
    # Check if config exists
    existing = await config_service.get_config_by_id(config_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Configuration with ID {config_id} not found")
    
    # Ensure the ID in the path matches the ID in the body
    if config.id != config_id:
        raise HTTPException(status_code=400, detail="ID in path must match ID in body")
    
    result = await config_service.update_config(config_id, config)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update configuration")
    
    return result

@router.delete("/configs/{config_id}", response_model= Dict[str, str])
async def delete_config(
    config_id: str,
    config_service: AgentConfigService = Depends(get_config_service)
):
    """Delete an agent configuration"""
    # Check if config exists
    existing = await config_service.get_config_by_id(config_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Configuration with ID {config_id} not found")
    
    result = await config_service.delete_config(config_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to delete configuration")
    
    return {"status": "success", "message": f"Configuration with ID {config_id} deleted"}
