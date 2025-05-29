import json
import os
from typing import List, Dict, Any, Optional
import logging
from pydantic import ValidationError

from app.genagent.models.config import AgentConfig
from app.genagent.repositories.config_repository import ConfigRepository

logger = logging.getLogger(__name__)

class AgentConfigService:
    """Service for managing agent configurations"""
    
    def __init__(self, repository: Optional[ConfigRepository] = None):
        """
        Initialize the config service
        
        Args:
            repository: Optional ConfigRepository instance (for dependency injection)
            config_file: Path to the config file (used if repository is not provided)
        """
        # Use provided repository or create a default one
        self.repository = repository or ConfigRepository(storage_type="file")
    
    async def get_all_configs(self) -> List[AgentConfig]:
        """Get all agent configurations as dictionaries (for backward compatibility)"""
        try:
            return await self.repository.get_all_configs()
        except Exception as e:
            logger.error(f"Error getting all configurations: {str(e)}")
            return []
         
    
    async def get_config_by_id(self, config_id: str) -> Optional[AgentConfig]:
        """Get a specific agent configuration by ID as a dictionary (for backward compatibility)"""
        try:
            return await self.repository.get_config_by_id(config_id)
        except Exception as e:
            logger.error(f"Error getting configuration by ID: {str(e)}")
            return None
       
    
    async def create_config(self, config_data: AgentConfig) -> Optional[AgentConfig]:
        """
        Create a new agent configuration
        
        Args:
            config_data: Configuration data as a dictionary
            
        Returns:
            The created configuration as a dictionary, or None if creation failed
        """
        try:
            # Create the configuration
            return await self.repository.create_config(config_data)
            
        except Exception as e:
            logger.error(f"Error creating configuration: {str(e)}")
            return None
    
    async def update_config(self, config_id: str, config_data: AgentConfig) -> Optional[AgentConfig]:
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

            return await self.repository.update_config(config_id, config_data)            
        except Exception as e:
            logger.error(f"Error updating configuration: {str(e)}")
            return None
    
    async def delete_config(self, config_id: str) -> bool:
        """
        Delete an agent configuration
        
        Args:
            config_id: ID of the configuration to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            return await self.repository.delete_config(config_id)
        except Exception as e:
            logger.error(f"Error deleting configuration: {str(e)}")
            return False 