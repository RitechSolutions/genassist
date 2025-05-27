import json
import logging
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.mapping_utils import to_agent_read
from app.dependencies.agents import get_agent_registry, get_agent_datasource_service
from app.modules.agents.data.datasource_service import AgentDataSourceService
from app.modules.agents.registry import AgentRegistry
from app.schemas.agent import AgentRead, QueryRequest
from app.services.agent_config import AgentConfigService
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.agent_tool import ToolService


router = APIRouter()


@router.post("/switch/{agent_id}", response_model=Dict[str, Any])
async def switch_agent(
        agent_id: UUID,
        config_service: AgentConfigService = Depends(),
        tool_service: ToolService = Depends(),
        agent_registry: AgentRegistry = Depends(get_agent_registry)
        ):
    """Switch to an agent with the specified ID"""
    # Get the agent configuration
    agent_model = await config_service.get_by_id_full(agent_id)
    agent_read: AgentRead = to_agent_read(agent_model)

    if agent_model.is_active:
        agent_registry.cleanup_agent(str(agent_id))
        await config_service.switch_agent(agent_id, switch=False)
        return {"status": "success", "message": "Agent switched to inactive"}
    else:
        tools_config = await tool_service.get_by_ids(agent_read.tool_ids)

        # Initialize the agent
        agent_registry.register_agent(str(agent_id), agent_model, tools_config)
        await config_service.switch_agent(agent_id, switch=True)
        return {"status": "success", "message": "Agent switched to active"}



@router.post("/{agent_id}/query/{thread_id}", response_model=Dict[str, Any])
async def query_agent(
        agent_id: UUID,
        thread_id: str,
    request: QueryRequest,
        config_service: AgentConfigService = Depends(),
    agent_registry: AgentRegistry = Depends(get_agent_registry),
    datasource_service: AgentDataSourceService = Depends(get_agent_datasource_service),
    knowledge_service: KnowledgeBaseService = Depends()
):
    return await run_query_agent_logic(
            str(agent_id), str(thread_id), request,
            config_service, agent_registry, datasource_service, knowledge_service
            )


async def run_query_agent_logic(
        agent_id: str,
        thread_id: str,
        request: QueryRequest,
        config_service: AgentConfigService = Depends(),
        agent_registry: AgentRegistry = Depends(get_agent_registry),
        datasource_service: AgentDataSourceService = Depends(get_agent_datasource_service),
        knowledge_service: KnowledgeBaseService = Depends()
        ):
    """Run a query against an initialized agent"""
    # If agent is not initialized, get config info
    agent_config = None

    if not agent_registry.is_agent_initialized(agent_id):
        agent_config = await config_service.get_by_id(agent_id)
        if not agent_config:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)

        if not agent_config.is_active:
            raise AppException(ErrorKey.AGENT_INACTIVE, status_code=400)

    agent = agent_registry.get_agent(agent_id)
    datasource_results = None
    #logging.info(f"Agent ID: {agent_id}, Thread ID: {thread_id}, agent_knowledge_bases: {len(agent.agent_model.agent_knowledge_bases)}")

    if agent and agent.agent_model.agent_knowledge_bases:
        # Pre-fetch knowledge results if needed
        knowledge_configs = await knowledge_service.get_by_ids([kb.knowledge_base_id for kb in agent.agent_model.agent_knowledge_bases])
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