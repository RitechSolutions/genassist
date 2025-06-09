import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.agents.registry import AgentRegistry
from app.schemas.agent import QueryRequest
from app.services.agent_config import AgentConfigService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/switch/{agent_id}", response_model=Dict[str, Any])
async def switch_agent(
        agent_id: UUID,
        config_service: AgentConfigService = Depends(),
        ):
    """Switch to an agent with the specified ID"""
    # Get the agent configuration
    agent_registry = AgentRegistry.get_instance()
    agent_model = await config_service.get_by_id_full(agent_id)
    if agent_model.is_active:
        agent_registry.cleanup_agent(str(agent_id))
        await config_service.switch_agent(agent_id, switch=False)
        return {"status": "success", "message": "Agent switched to inactive"}
    else:
        # Initialize the agent
        logger.info(f"Initializing agent {agent_id}")
        logger.info(f"Agent model: {agent_model.__dict__}")
        agent_registry.register_agent(str(agent_id), agent_model)
        await config_service.switch_agent(agent_id, switch=True)
        return {"status": "success", "message": "Agent switched to active"}



@router.post("/{agent_id}/query/{thread_id}", response_model=Dict[str, Any])
async def query_agent(
        agent_id: UUID,
        thread_id: str,
        request: QueryRequest,
):
    return await run_query_agent_logic(str(agent_id), request.query, {**(request.metadata if request.metadata else {}), "thread_id": thread_id})


async def run_query_agent_logic(
        agent_id: str,
        user_query: str,
        metadata: Optional[Dict[str, Any]] = None,
        ):
    """Run a query against an initialized agent"""
    # If agent is not initialized, get config info
    agent_registry = AgentRegistry.get_instance()

    if not agent_registry.is_agent_initialized(agent_id):
        raise AppException(ErrorKey.AGENT_INACTIVE, status_code=400)

    agent = agent_registry.get_agent(agent_id)
    # Agent.run_query is not an async method, so don't use await
    result = await agent.get_executor().execute(
            user_query=user_query,
            metadata=metadata
            )
    backward_compatibility_result = {
        
                "status": result.get("status"),
                "response": result.get("output"),
                "agent_id": agent_id,
                "thread_id": metadata.get("thread_id"),
                "rag_used": False
            
    }
    logger.info(f"Result: {result}")
    logger.info(f"Backward compatibility result: {backward_compatibility_result}")
    if backward_compatibility_result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return backward_compatibility_result