<<<<<<< HEAD

from typing import List,Optional
import logging
from app.repositories.base_repository import BaseRepository
from app.schemas.agent_config import AgentConfig
=======
import logging
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.utils import generate_password
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models import AgentModel
from app.db.session import get_db
from app.repositories.agent import AgentRepository
from app.repositories.user_types import UserTypesRepository
from app.schemas.agent import AgentCreate, AgentUpdate
from app.schemas.workflow import get_base_workflow
from app.services.operators import OperatorService
from app.services.workflow import WorkflowService

>>>>>>> development

logger = logging.getLogger(__name__)

class AgentConfigService:
    """Service for managing agent configurations"""
<<<<<<< HEAD
    
    def __init__(self, repository: Optional[BaseRepository[AgentConfig]] = None):
        self.repository = repository 
    
    async def get_all(self) -> List[AgentConfig]:
        """Get all agent configurations as dictionaries (for backward compatibility)"""
        try:
            return await self.repository.get_all()
        except Exception as e:
            logger.error(f"Error getting all configurations: {str(e)}")
            return []
         
    
    async def get_by_id(self, config_id: str) -> Optional[AgentConfig]:
        """Get a specific agent configuration by ID as a dictionary (for backward compatibility)"""
        try:
            return await self.repository.get_by_id(config_id)
        except Exception as e:
            logger.error(f"Error getting configuration by ID: {str(e)}")
            return None
       
    
    async def create(self, config_data: AgentConfig) -> Optional[AgentConfig]:
        """
        Create a new agent configuration
        
        Args:
            config_data: Configuration data as a dictionary
            
        Returns:
            The created configuration as a dictionary, or None if creation failed
        """
        try:
            # Create the configuration
            return await self.repository.create(config_data)
            
        except Exception as e:
            logger.error(f"Error creating configuration: {str(e)}")
            return None
    
    async def update(self, config_id: str, config_data: AgentConfig) -> Optional[AgentConfig]:
        """
        Update an existing agent configuration
        
        Args:
            config_id: ID of the configuration to update
            config_data: Updated configuration data as a dictionary
            
        Returns:
            The updated configuration as a dictionary, or None if update failed
        """
        try:
            # Ensure the ID doesn't change
            config_data.id = config_id

            return await self.repository.update(config_id, config_data)            
        except Exception as e:
            logger.error(f"Error updating configuration: {str(e)}")
            return None
    
    async def delete(self, config_id: str) -> bool:
=======


    def __init__(self, repository: AgentRepository = Depends(),
                 operator_service: OperatorService = Depends(),
                 workflow_service: WorkflowService = Depends(),
                 user_types_repository: UserTypesRepository = Depends(),
                 db: AsyncSession = Depends(get_db),
                 ):
        self.repository = repository
        self.operator_service = operator_service
        self.workflow_service = workflow_service
        self.user_types_repository = user_types_repository
        self.db: AsyncSession = db


    async def get_all_full(self) -> list[AgentModel]:
        """Get all agent configurations as dictionaries (for backward compatibility)"""
        return await self.repository.get_all_full()


    async def get_by_id_full(self, agent_id: UUID) -> AgentModel:
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


    async def create(self, agent_create: AgentCreate) -> AgentModel:
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
        
        workflow_data = get_base_workflow(self, name=agent_data.get("name"))
        base_workflow = await self.workflow_service.create(workflow_data)
        agent_data["workflow_id"] = base_workflow.id
        agent_data["is_active"] = int(agent_data.get("is_active", False))
        agent_data["operator_id"] = operator.id
        # Store as semi-colon separated string
        agent_data["possible_queries"] = ";".join(agent_data.get("possible_queries", ""))

        orm_agent = AgentModel(**agent_data)

        created_agent = await self.repository.create(orm_agent)
        await self.db.refresh(created_agent)

            #await self.db.commit()
        
        return created_agent

    async def _operator_user_type_id(self) -> UUID:
        # small helper; cache or query UserTypesRepository as you already do
        return (await self.user_types_repository.get_by_name("console")).id


    async def update(
            self, agent_id: UUID, agent_update: AgentUpdate
            ) -> AgentModel:
        agent: AgentModel | None = await self.repository.get_by_id(agent_id)
        if not agent:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)

        scalar_changes = agent_update.model_dump(
                exclude_unset=True,
                )
        if "is_active" in scalar_changes:
            scalar_changes["is_active"] = int(scalar_changes["is_active"])
        # Store as semi-colon separated string
        if "possible_queries" in scalar_changes:
            scalar_changes["possible_queries"] = ";".join(scalar_changes["possible_queries"])

        for field, value in scalar_changes.items():
            setattr(agent, field, value)

        updated = await self.repository.update(
                agent
                )
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
>>>>>>> development
        """
        Delete an agent configuration
        
        Args:
<<<<<<< HEAD
            config_id: ID of the configuration to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            return await self.repository.delete(config_id)
        except Exception as e:
            logger.error(f"Error deleting configuration: {str(e)}")
            return False 
=======
            agent_id: ID of the agent to delete
        """
        agent_delete = await self.repository.get_by_id(agent_id)
        if not agent_delete:
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        await self.repository.soft_delete(agent_delete)


    async def get_by_user_id(self, user_id: UUID) -> AgentModel:
        agent = await self.repository.get_by_user_id(user_id)
        if not agent:
            logger.debug("No agent for userid:"+str(user_id))
            raise AppException(ErrorKey.AGENT_NOT_FOUND, status_code=404)
        return agent

>>>>>>> development
