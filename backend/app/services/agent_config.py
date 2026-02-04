import logging
from typing import Optional
from uuid import UUID

from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.utils import generate_password
from app.cache.redis_cache import invalidate_agent_cache, make_key_builder
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models import AgentModel
from app.db.utils.sql_alchemy_utils import null_unloaded_attributes
from app.repositories.agent import AgentRepository
from app.repositories.user_types import UserTypesRepository
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.schemas.agent_security_settings import AgentSecuritySettingsCreate, AgentSecuritySettingsUpdate
from app.db.models import AgentSecuritySettingsModel
from app.schemas.workflow import WorkflowUpdate, get_base_workflow
from app.services.operators import OperatorService
from app.services.workflow import WorkflowService


logger = logging.getLogger(__name__)

agent_id_key_builder = make_key_builder("agent_id")
user_id_key_builder = make_key_builder("user_id")

@inject
class AgentConfigService:
    """Service for managing agent configurations"""

    def __init__(self, repository: AgentRepository,
                 operator_service: OperatorService,
                 workflow_service: WorkflowService,
                 user_types_repository: UserTypesRepository,
                 db: AsyncSession,
                 ):
        self.repository = repository
        self.operator_service = operator_service
        self.workflow_service = workflow_service
        self.user_types_repository = user_types_repository
        self.db: AsyncSession = db

    async def get_all_full(self) -> list[AgentModel]:
        """Get all agent configurations as dictionaries (for backward compatibility)"""
        return await self.repository.get_all_full()

    @cache(
            expire=300,
            namespace="agents:get_by_id_full",
            key_builder=agent_id_key_builder,
            coder=PickleCoder
            )
    async def get_by_id_full(self, agent_id: UUID) -> AgentRead:
        agent = await self.repository.get_by_id_full(agent_id)
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)

        # Convert to Pydantic model for caching (avoids pickling SQLAlchemy objects)
        # The model_validator in AgentRead handles workflow conversion automatically
        null_unloaded_attributes(agent)
        agent_read = AgentRead.model_validate(agent)

        return agent_read

    async def get_by_id_cached(self, agent_id: UUID) -> AgentModel:
        agent = await self.repository.get_by_id_full(agent_id)
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        return agent

    async def get_by_id(self, agent_id: UUID) -> AgentModel:
        """Get a specific agent configuration by ID as a dictionary (for backward compatibility)"""

        agent = await self.repository.get_by_id(agent_id)
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        return agent

    async def create(self, agent_create: AgentCreate, user_id: UUID) -> AgentModel:
        # ── 0. generate console credentials ───────────────────────────
        pwd_plain = generate_password()
        email = f"{generate_password(6)}@genassist.ritech.io"
        # async with self.db.begin_nested():
        # ── 1. Operator/User for this agent (console) ─────────────────
        operator = await self.operator_service.create_from_agent(
            agent_name=agent_create.name,
            email=email,
            plain_password=pwd_plain,
        )

        # ── 2. build AgentModel (operator_id now known) ───────────────
        agent_data = agent_create.model_dump(
            exclude_unset=True,
        )
        
        # Extract security_settings if present
        security_settings_data = agent_data.pop("security_settings", None)

        if not agent_create.workflow_id:
            workflow_data = get_base_workflow(name=agent_data.get("name"))
            base_workflow = await self.workflow_service.create(workflow_data)
            agent_data["workflow_id"] = base_workflow.id
        else:
            workflow = await self.workflow_service.get_by_id(agent_create.workflow_id)
            agent_data["workflow_id"] = workflow.id

        agent_data["is_active"] = int(agent_data.get("is_active", False))
        agent_data["operator_id"] = operator.id
        # Store as semi-colon separated string
        agent_data["possible_queries"] = ";".join(
            agent_data.get("possible_queries", ""))
        agent_data["thinking_phrases"] = ";".join(
            agent_data.get("thinking_phrases", ""))
        # Handle image blob - if it's provided, it should already be bytes
        if "welcome_image" in agent_data and agent_data["welcome_image"] is not None:
            if isinstance(agent_data["welcome_image"], str):
                # If it's a string, convert to bytes (assuming it's base64 encoded)
                import base64
                agent_data["welcome_image"] = base64.b64decode(agent_data["welcome_image"])
        orm_agent = AgentModel(**agent_data)

        created_agent = await self.repository.create(orm_agent)
        
        # Create security settings (always create with defaults if not provided)
        if security_settings_data:
            security_settings = AgentSecuritySettingsModel(
                agent_id=created_agent.id,
                **AgentSecuritySettingsCreate(**security_settings_data).model_dump(exclude_unset=True)
            )
        else:
            # Create with default token_based_auth=false
            security_settings = AgentSecuritySettingsModel(
                agent_id=created_agent.id,
                token_based_auth=False
            )
        self.db.add(security_settings)
        await self.db.flush()
        
        await self.db.refresh(created_agent, attribute_names=['operator', 'security_settings'])

        old_workflow = await self.workflow_service.get_by_id(created_agent.workflow_id)
        await self.workflow_service.update(created_agent.workflow_id, WorkflowUpdate(name=old_workflow.name,
                                                                                     description=old_workflow.description,
                                                                                     nodes=old_workflow.nodes,
                                                                                     edges=old_workflow.edges,
                                                                                     executionState=old_workflow.executionState,
                                                                                     user_id=user_id,
                                                                                     version=old_workflow.version,
                                                                                     agent_id=created_agent.id))

        # await self.db.commit()
        null_unloaded_attributes(created_agent)
        return created_agent

    async def _operator_user_type_id(self) -> UUID:
        # small helper; cache or query UserTypesRepository as you already do
        return (await self.user_types_repository.get_by_name("console")).id

    async def update(
            self, agent_id: UUID, agent_update: AgentUpdate
    ) -> AgentModel:
        agent: AgentModel | None = await self.repository.get_by_id_full(agent_id)

        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        
        # Store user_id before any changes
        user_id = agent.operator.user.id

        scalar_changes = agent_update.model_dump(
            exclude_unset=True,
        )
        
        # Handle security_settings separately
        security_settings_update = scalar_changes.pop("security_settings", None)
        
        if "is_active" in scalar_changes:
            scalar_changes["is_active"] = int(scalar_changes["is_active"])
        # Store as semi-colon separated string
        if "possible_queries" in scalar_changes:
            scalar_changes["possible_queries"] = ";".join(
                scalar_changes["possible_queries"])
        if "thinking_phrases" in scalar_changes:
            scalar_changes["thinking_phrases"] = ";".join(
                scalar_changes["thinking_phrases"])
        # Handle image blob
        if "welcome_image" in scalar_changes and scalar_changes["welcome_image"] is not None:
            if isinstance(scalar_changes["welcome_image"], str):
                # If it's a string, convert to bytes (assuming it's base64 encoded)
                import base64
                scalar_changes["welcome_image"] = base64.b64decode(scalar_changes["welcome_image"])
        for field, value in scalar_changes.items():
            setattr(agent, field, value)

        # Update or create security settings
        if security_settings_update is not None:
            if agent.security_settings:
                # Update existing security settings
                security_update_data = AgentSecuritySettingsUpdate(**security_settings_update).model_dump(exclude_unset=True)
                for field, value in security_update_data.items():
                    setattr(agent.security_settings, field, value)
            else:
                # Create new security settings
                security_settings = AgentSecuritySettingsModel(
                    agent_id=agent.id,
                    **AgentSecuritySettingsCreate(**security_settings_update).model_dump(exclude_unset=True)
                )
                self.db.add(security_settings)
                agent.security_settings = security_settings

        updated = await self.repository.update(
            agent
        )
        
        # Refresh the agent with security_settings relationship loaded
        await self.db.refresh(updated, ["security_settings"])
        null_unloaded_attributes(updated)
        
        # Invalidate cache after update to ensure fresh data on next fetch
        await invalidate_agent_cache(agent_id, user_id)

        return updated

    async def switch_agent(
            self, agent_id: UUID, switch: bool
    ) -> AgentModel:
        agent: AgentModel | None = await self.repository.get_by_id(agent_id)
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        agent.is_active = int(switch)

        return await self.repository.update(agent)

    async def delete(self, agent_id: UUID) -> None:
        """
        Delete an agent configuration

        Args:
            agent_id: ID of the agent to delete
        """

        agent_delete = await self.repository.get_by_id_full(agent_id)
        if not agent_delete:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        await self.repository.soft_delete(agent_delete)

        # Invalidate cache entries for this agent
        await invalidate_agent_cache(agent_id, agent_delete.operator.user.id)

    @cache(
            expire=300,
            namespace="agents:get_by_user_id",
            key_builder=user_id_key_builder,
            coder=PickleCoder
            )
    async def get_by_user_id(self, user_id: UUID) -> AgentRead:
        """Get agent by user ID and cache the result"""
        agent = await self.repository.get_by_user_id(user_id)
        if not agent:
            logger.debug("No agent for userid:"+str(user_id))
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)

        # Convert to Pydantic model for caching (avoids pickling SQLAlchemy objects)
        null_unloaded_attributes(agent)
        agent_read = AgentRead.model_validate(agent)

        return agent_read

    async def upload_welcome_image(self, agent_id: UUID, image_data: bytes) -> AgentModel:
        """Upload welcome image for an agent"""
        agent = await self.repository.get_by_id(agent_id)
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)

        agent.welcome_image = image_data
        return await self.repository.update(agent)

    async def get_welcome_image(self, agent_id: UUID) -> Optional[bytes]:
        """Get welcome image for an agent"""
        agent = await self.repository.get_by_id(agent_id)
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        return agent.welcome_image

    async def delete_welcome_image(self, agent_id: UUID) -> AgentModel:
        """Delete welcome image for an agent"""
        agent = await self.repository.get_by_id(agent_id)
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)

        agent.welcome_image = None
        return await self.repository.update(agent)

    async def get_by_operator_id(self, operator_id: UUID) -> AgentModel:
        """Get agent by operator ID with security_settings eagerly loaded."""
        agent = await self.repository.get_by_operator_id(
            operator_id, eager=("security_settings",)
        )
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        return agent