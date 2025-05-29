import json
import os
from typing import List, Dict, Any, Optional
import logging
from pydantic import ValidationError

from app.genagent.models.tool import ToolConfig
from app.genagent.repositories.tool_repository import ToolRepository

logger = logging.getLogger(__name__)

class ToolService:
    """Service for managing tools"""
    
    def __init__(self, repository: Optional[ToolRepository] = None):
        """
        Initialize the tool service
        
        Args:
            repository: Optional ToolRepository instance (for dependency injection)
            tools_file: Path to the tools file (used if repository is not provided)
        """
        # Use provided repository or create a default one
        self.repository = repository or ToolRepository(storage_type="file")
    
    async def get_all_tools(self) -> List[ToolConfig]:
        """Get all tools as validated ToolConfig objects"""
        try:
            tools = await self.repository.get_all_tools()
            return tools
        except Exception as e:
            logger.error(f"Error loading tools: {str(e)}")
            return []
    
    
    async def get_tool_by_id(self, tool_id: str) -> Optional[ToolConfig]:
        """Get a specific tool by ID as a validated ToolConfig object"""
        tool = await self.repository.get_tool_by_id(tool_id)
        return tool
    

    
    async def get_tools_by_ids(self, tool_ids: List[str]) -> List[ToolConfig]:
        """Get multiple tools by their IDs as validated ToolConfig objects"""
        if not tool_ids:
            return []
            
        return await self.repository.get_tools_by_ids(tool_ids)
    
    async def create_tool(self, tool_data: ToolConfig) -> Optional[ToolConfig]:
        """
        Create a new tool
        
        Args:
            tool_data: Tool configuration as a dictionary
            
        Returns:
            The created tool as a dictionary, or None if creation failed
        """
        try:
            
            created_tool = await self.repository.create_tool(tool_data)
            return created_tool
            
        except Exception as e:
            logger.error(f"Error creating tool: {str(e)}")
            return None
    
    async def update_tool(self, tool_id: str, tool_data: ToolConfig) -> Optional[ToolConfig]:
        """
        Update an existing tool
        
        Args:
            tool_id: ID of the tool to update
            tool_data: Updated tool configuration as a dictionary
            
        Returns:
            The updated tool as a dictionary, or None if update failed
        """
        try:
            
            # Ensure the ID doesn't change
            tool_data.id = tool_id
            
            # Update the tool
            updated_tool = await self.repository.update_tool(tool_id, tool_data)
            return updated_tool
            
        except Exception as e:
            logger.error(f"Error updating tool: {str(e)}")
            return None
    
    async def delete_tool(self, tool_id: str) -> bool:
        """
        Delete a tool
        
        Args:
            tool_id: ID of the tool to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            return await self.repository.delete_tool(tool_id)
        except Exception as e:
            logger.error(f"Error deleting tool: {str(e)}")
            return False 