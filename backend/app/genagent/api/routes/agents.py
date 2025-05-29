from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.genagent.services.agent_config_service import AgentConfigService
from app.genagent.services.knowledge_service import KnowledgeService
from app.genagent.services.tool_service import ToolService
from app.genagent.core.dependencies import  get_config_service, get_tool_service, get_agent_registry, get_datasource_service, get_knowledge_service
from app.genagent.agents.registry import AgentRegistry
from app.genagent.agents.data.datasource_service import DataSourceService

router = APIRouter()

class QueryRequest(BaseModel):
    query: str


@router.post("/switch/{agent_id}")
async def switch_agent(
    agent_id: str,
    config_service: AgentConfigService = Depends(get_config_service),
    tool_service: ToolService = Depends(get_tool_service),
    agent_registry: AgentRegistry = Depends(get_agent_registry)
):
    """Switch to an agent with the specified ID"""
    # Get the agent configuration
    agent_config = await config_service.get_config_by_id(agent_id)
    if not agent_config:
        raise HTTPException(status_code=404, detail=f"Agent with ID {agent_id} not found")
    
    if agent_config.is_active == True:
        agent_registry.cleanup_agent(agent_id)
        agent_config.is_active = False
        await config_service.update_config(agent_id, agent_config)
        return {"status": "success", "message": "Agent switched to inactive"}
        
        # Get the tools for the agent
    
    tools_config = await tool_service.get_tools_by_ids(agent_config.tool_ids)
        
    # Initialize the agent
    agent_registry.register_agent(agent_id, agent_config, tools_config)
    agent_config.is_active = True
    await config_service.update_config(agent_id, agent_config)
    return {"status": "success", "message": "Agent switched to active"}



@router.post("/{agent_id}/query/{thread_id}", response_model=Dict[str, Any])
async def query_agent(
    agent_id: str,
    thread_id: str,
    request: QueryRequest,
    config_service: AgentConfigService = Depends(get_config_service),
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    datasource_service: DataSourceService = Depends(get_datasource_service),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """Run a query against an initialized agent"""
    # If agent is not initialized, get config info
    agent_config = None    
    
    if not agent_registry.is_agent_initialized(agent_id):
        agent_config = await config_service.get_config_by_id(agent_id)
        if not agent_config:
            raise HTTPException(status_code=404, detail=f"Agent with ID {agent_id} not found")
        
        if agent_config.is_active == False:
            raise HTTPException(status_code=400, detail=f"Agent with ID {agent_id} is not active")





    agent = agent_registry.get_agent(agent_id)
    datasource_results = None
    if agent and agent.config.knowledge_base_ids:
        # Pre-fetch knowledge results if needed
        knowledge_configs = await knowledge_service.get_items_by_ids(agent.config.knowledge_base_ids)
        datasource_results = await datasource_service.search_knowledge(
            query=request.query,
            docs_config=knowledge_configs,
            format_results=True
        )
    
    # Agent.run_query is not an async method, so don't use await
    result = agent.run_query(
        thread_id, 
        request.query, 
        datasource_results
    )
    
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result 