import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from injector import inject
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.mcp_server import MCPServerModel, MCPServerWorkflowModel

logger = logging.getLogger(__name__)


@inject
class MCPServerRepository:
    """Repository for MCP Server database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        user_id: UUID,
        auth_type: str,
        auth_values: Dict[str, Any],
        description: Optional[str] = None,
        is_active: int = 1,
        workflows: Optional[List[dict]] = None,
    ) -> MCPServerModel:
        """Create a new MCP server."""
        mcp_server = MCPServerModel(
            name=name,
            auth_type=auth_type,
            auth_values=auth_values,
            user_id=user_id,
            description=description,
            is_active=is_active,
        )

        self.db.add(mcp_server)
        await self.db.flush()

        if workflows:
            for wf_data in workflows:
                workflow = MCPServerWorkflowModel(
                    mcp_server_id=mcp_server.id,
                    workflow_id=wf_data["workflow_id"],
                    tool_name=wf_data["tool_name"],
                    tool_description=wf_data["tool_description"],
                )
                self.db.add(workflow)

        await self.db.commit()
        await self.db.refresh(mcp_server)
        return await self.get_by_id(mcp_server.id)

    async def get_by_id(self, mcp_server_id: UUID, user_id: Optional[UUID] = None) -> Optional[MCPServerModel]:
        """Fetch MCP server by ID, optionally filtered by user."""
        query = (
            select(MCPServerModel)
            .options(selectinload(MCPServerModel.workflows).selectinload(MCPServerWorkflowModel.workflow))
            .where(
                and_(
                    MCPServerModel.id == mcp_server_id,
                    MCPServerModel.is_deleted == 0,
                    MCPServerModel.user_id == user_id if user_id else True,
                )
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_api_key_hash(self, api_key_hash: str) -> Optional[MCPServerModel]:
        """Fetch MCP server by API key hash (for authentication)."""
        j = MCPServerModel.auth_values
        query = (
            select(MCPServerModel)
            .options(selectinload(MCPServerModel.workflows).selectinload(MCPServerWorkflowModel.workflow))
            .where(
                and_(
                    MCPServerModel.auth_type == "api_key",
                    j["api_key_hash"].astext == api_key_hash,
                    MCPServerModel.is_deleted == 0,
                )
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_oauth_client_id_hash(
        self, oauth_client_id_hash: str
    ) -> Optional[MCPServerModel]:
        """
        Fetch an OAuth2 MCP server by ``auth_values.oauth2_client_id_hash`` only.

        Issuer and audience for inbound JWT verification come from the matched row.
        """
        if not oauth_client_id_hash:
            return None
        j = MCPServerModel.auth_values
        query = (
            select(MCPServerModel)
            .options(selectinload(MCPServerModel.workflows).selectinload(MCPServerWorkflowModel.workflow))
            .where(
                and_(
                    MCPServerModel.auth_type == "oauth2",
                    j["oauth2_client_id_hash"].astext == oauth_client_id_hash,
                    MCPServerModel.is_deleted == 0,
                )
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all(self, user_id: Optional[UUID] = None) -> List[MCPServerModel]:
        """Fetch all MCP servers, optionally filtered by user."""
        query = (
            select(MCPServerModel)
            .options(selectinload(MCPServerModel.workflows).selectinload(MCPServerWorkflowModel.workflow))
            .where(
                and_(
                    MCPServerModel.is_deleted == 0,
                    MCPServerModel.user_id == user_id if user_id else True,
                )
            )
            .order_by(MCPServerModel.created_at.asc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_name(self, name: str, user_id: UUID) -> Optional[MCPServerModel]:
        """Check if a server with the given name exists for the user."""
        query = select(MCPServerModel).where(
            and_(
                MCPServerModel.name == name,
                MCPServerModel.user_id == user_id,
                MCPServerModel.is_deleted == 0,
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def update(
        self,
        mcp_server_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        auth_type: Optional[str] = None,
        auth_values: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        is_active: Optional[int] = None,
        workflows: Optional[List[dict]] = None,
    ) -> Optional[MCPServerModel]:
        """Update an MCP server."""
        mcp_server = await self.get_by_id(mcp_server_id, user_id)
        if not mcp_server:
            return None

        if name is not None:
            mcp_server.name = name
        if auth_type is not None:
            mcp_server.auth_type = auth_type
        if auth_values is not None:
            mcp_server.auth_values = auth_values
        if description is not None:
            mcp_server.description = description
        if is_active is not None:
            mcp_server.is_active = is_active

        if workflows is not None:
            existing_workflows_query = select(MCPServerWorkflowModel).where(
                MCPServerWorkflowModel.mcp_server_id == mcp_server_id
            )
            existing_workflows_result = await self.db.execute(existing_workflows_query)
            existing_workflows = {wf.workflow_id: wf for wf in existing_workflows_result.scalars().all()}
            incoming_workflows = {wf_data["workflow_id"]: wf_data for wf_data in workflows}

            for workflow_id, wf in existing_workflows.items():
                if workflow_id not in incoming_workflows:
                    await self.db.delete(wf)

            for workflow_id, wf_data in incoming_workflows.items():
                if workflow_id in existing_workflows:
                    existing = existing_workflows[workflow_id]
                    if existing.tool_name != wf_data["tool_name"]:
                        existing.tool_name = wf_data["tool_name"]
                    if existing.tool_description != wf_data["tool_description"]:
                        existing.tool_description = wf_data["tool_description"]
                else:
                    self.db.add(
                        MCPServerWorkflowModel(
                            mcp_server_id=mcp_server.id,
                            workflow_id=workflow_id,
                            tool_name=wf_data["tool_name"],
                            tool_description=wf_data["tool_description"],
                        )
                    )

        await self.db.commit()
        await self.db.refresh(mcp_server)
        return await self.get_by_id(mcp_server_id, user_id)

    async def delete(self, mcp_server_id: UUID, user_id: UUID) -> bool:
        """Soft delete an MCP server."""
        mcp_server = await self.get_by_id(mcp_server_id, user_id)
        if not mcp_server:
            return False
        mcp_server.is_deleted = 1
        await self.db.commit()
        await self.db.refresh(mcp_server)
        return True
