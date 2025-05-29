import logging
from typing import Optional, List, Union, Type

from app.genagent.models.config import AgentConfig
from app.genagent.repositories.base_repository import BaseRepository
from app.genagent.repositories.file_repository import FileRepository
from app.genagent.repositories.db_repository import DbRepository

logger = logging.getLogger(__name__)

class ConfigRepository:
    """Repository for managing Agent configurations"""
    
    def __init__(self, storage_type: str = "file", file_path: str = "agents_config/agent_config.json", db_connection=None):
        """
        Initialize the configuration repository
        
        Args:
            storage_type: Type of storage to use ('file' or 'db')
            file_path: Path to the JSON file for storage (if using file storage)
            db_connection: Database connection (if using database storage)
        """
        self.storage_type = storage_type
        self.model_class = AgentConfig
        
        # Create appropriate repository implementation
        if storage_type == "file":
            self.repository: BaseRepository[AgentConfig] = FileRepository(file_path, AgentConfig)
        elif storage_type == "db":
            self.repository = DbRepository(AgentConfig, db_connection)
        else:
            raise ValueError(f"Invalid storage type: {storage_type}. Must be 'file' or 'db'")
    
    async def get_all_configs(self) -> List[AgentConfig]:
        """Get all agent configurations"""
        return await self.repository.get_all()
    
    async def get_config_by_id(self, config_id: str) -> Optional[AgentConfig]:
        """Get a specific agent configuration by ID"""
        return await self.repository.get_by_id(config_id)
    
    async def get_configs_by_ids(self, config_ids: List[str]) -> List[AgentConfig]:
        """Get multiple agent configurations by their IDs"""
        return await self.repository.get_by_ids(config_ids)
    
    async def create_config(self, config: AgentConfig) -> Optional[AgentConfig]:
        """Create a new agent configuration"""
        return await self.repository.create(config)
    
    async def update_config(self, config_id: str, config: AgentConfig) -> Optional[AgentConfig]:
        """Update an existing agent configuration"""
        return await self.repository.update(config_id, config)
    
    async def delete_config(self, config_id: str) -> bool:
        """Delete an agent configuration"""
        return await self.repository.delete(config_id) 