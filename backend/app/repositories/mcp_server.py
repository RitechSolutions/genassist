from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from uuid import UUID
from injector import inject
import logging

from app.db.models.mcp_server import MCPServerModel, MCPServerWorkflowModel
from app.auth.utils import get_current_user_id

logger = logging.getLogger(__name__)


@inject
class MCPServerRepository:
    """Repository for MCP Server database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        api_key_encrypted: str,
        api_key_hash: str,
        user_id: UUID,
        description: Optional[str] = None,
        is_active: int = 1,
        workflows: Optional[List[dict]] = None,
    ) -> MCPServerModel:
        """Create a new MCP server."""
        mcp_server = MCPServerModel(
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_key_hash=api_key_hash,
            user_id=user_id,
            description=description,
            is_active=is_active,
        )

        self.db.add(mcp_server)
        await self.db.flush()  # Flush to get the ID

        # Create workflow associations
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
        return await self.get_by_id(mcp_server.id)  # Return with workflows loaded

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
        query = (
            select(MCPServerModel)
            .options(selectinload(MCPServerModel.workflows).selectinload(MCPServerWorkflowModel.workflow))
            .where(
                and_(
                    MCPServerModel.api_key_hash == api_key_hash,
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
        api_key_encrypted: Optional[str] = None,
        api_key_hash: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[int] = None,
        workflows: Optional[List[dict]] = None,
    ) -> Optional[MCPServerModel]:
        """Update an MCP server."""
        mcp_server = await self.get_by_id(mcp_server_id, user_id)
        if not mcp_server:
            return None

        # Update basic fields
        if name is not None:
            mcp_server.name = name
        if api_key_encrypted is not None:
            mcp_server.api_key_encrypted = api_key_encrypted
        if api_key_hash is not None:
            mcp_server.api_key_hash = api_key_hash
        if description is not None:
            mcp_server.description = description
        if is_active is not None:
            mcp_server.is_active = is_active

        # Update workflows if provided
        if workflows is not None:
            # Delete existing workflows
            existing_workflows_query = select(MCPServerWorkflowModel).where(
                MCPServerWorkflowModel.mcp_server_id == mcp_server_id
            )
            existing_workflows_result = await self.db.execute(existing_workflows_query)
            for wf in existing_workflows_result.scalars().all():
                await self.db.delete(wf)

            # Create new workflows
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

