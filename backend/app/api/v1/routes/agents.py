import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi_injector import Injected
from app.core.permissions.constants import Permissions as P
from app.auth.dependencies import auth, permissions
from app.cache.redis_cache import invalidate_agent_cache
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.registry import RegistryItem
from app.schemas.agent import QueryRequest
from app.services.agent_config import AgentConfigService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/switch/{agent_id}", response_model=Dict[str, Any], dependencies=[
        Depends(auth),
        Depends(permissions(P.Agent.SWITCH))
    ])
async def switch_agent(
        agent_id: UUID,
        config_service: AgentConfigService = Injected(AgentConfigService),
        ):
    """
    Switch an agent between active and inactive states.

    Updates the database directly - all server instances will see the change
    immediately on the next agent query (database is source of truth).

    Invalidates the cache for this agent to ensure fresh data is fetched.
    """
    # Get the agent configuration
    agent_model = await config_service.get_by_id_full(agent_id)
    if agent_model.is_active:
        await config_service.switch_agent(agent_id, switch=False)
        # Invalidate cache after updating the agent
        await invalidate_agent_cache(agent_id, agent_model.operator.user.id)
        logger.info(f"Agent {agent_id} switched to inactive and cache invalidated")
        return {"status": "success", "message": "Agent switched to inactive"}
    else:
        await config_service.switch_agent(agent_id, switch=True)
        # Invalidate cache after updating the agent
        await invalidate_agent_cache(agent_id, agent_model.operator.user.id)
        logger.info(f"Agent {agent_id} switched to active and cache invalidated")
        return {"status": "success", "message": "Agent switched to active"}


@router.post("/{agent_id}/query/{thread_id}", response_model=Dict[str, Any], dependencies=[
        Depends(auth),
    ])
async def query_agent(
        agent_id: UUID,
        thread_id: str,
        request: QueryRequest,
        agent_service: AgentConfigService = Injected(AgentConfigService),
):
    return await run_query_agent_logic(agent_service, str(agent_id), request.query, {**(request.metadata if
                                                                                        request.metadata else {}), "thread_id": thread_id})


async def run_query_agent_logic(
        agent_service: AgentConfigService,
        agent_id: str,
        session_message: str,
        metadata: Optional[Dict[str, Any]] = None,
        ):
    """
    Run a query against an agent.

    Fetches agent from database on demand - always gets latest configuration.
    """

    # Fetch agent from database and execute
    agent = await agent_service.get_by_id_full(UUID(agent_id))
    if not agent.is_active:
        raise AppException(ErrorKey.AGENT_INACTIVE, status_code=400)

    agent = RegistryItem(agent)

    logger.info(f"Workflow Metadata: {metadata}")

    result = await agent.execute(
            session_message=session_message,
            metadata=metadata
            )
    logger.info(f"Workflow Final Result: {result}")
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