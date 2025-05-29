import logging
from typing import Optional, List, Union, Type

from app.genagent.models.tool import ToolConfig
from app.genagent.repositories.base_repository import BaseRepository
from app.genagent.repositories.file_repository import FileRepository
from app.genagent.repositories.db_repository import DbRepository

logger = logging.getLogger(__name__)

class ToolRepository:
    """Repository for managing Tool configurations"""
    
    def __init__(self, storage_type: str = "file", file_path: str = "agents_config/tools.json", db_connection=None):
        """
        Initialize the tool repository
        
        Args:
            storage_type: Type of storage to use ('file' or 'db')
            file_path: Path to the JSON file for storage (if using file storage)
            db_connection: Database connection (if using database storage)
        """
        self.storage_type = storage_type
        self.model_class = ToolConfig
        
        # Create appropriate repository implementation
        if storage_type == "file":
            self.repository: BaseRepository[ToolConfig] = FileRepository(file_path, ToolConfig)
        elif storage_type == "db":
            self.repository = DbRepository(ToolConfig, db_connection)
        else:
            raise ValueError(f"Invalid storage type: {storage_type}. Must be 'file' or 'db'")
    
    async def get_all_tools(self) -> List[ToolConfig]:
        """Get all tool configurations"""
        return await self.repository.get_all()
    
    async def get_tool_by_id(self, tool_id: str) -> Optional[ToolConfig]:
        """Get a specific tool by ID"""
        return await self.repository.get_by_id(tool_id)
    
    async def get_tools_by_ids(self, tool_ids: List[str]) -> List[ToolConfig]:
        """Get multiple tools by their IDs"""
        return await self.repository.get_by_ids(tool_ids)
    
    async def create_tool(self, tool: ToolConfig) -> Optional[ToolConfig]:
        """Create a new tool"""
        return await self.repository.create(tool)
    
    async def update_tool(self, tool_id: str, tool: ToolConfig) -> Optional[ToolConfig]:
        """Update an existing tool"""
        return await self.repository.update(tool_id, tool)
    
    async def delete_tool(self, tool_id: str) -> bool:
        """Delete a tool"""
        return await self.repository.delete(tool_id) 