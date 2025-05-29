import logging
from typing import Optional, List, Union, Type

from app.genagent.models.knowledge import KnowledgeItem
from app.genagent.repositories.base_repository import BaseRepository
from app.genagent.repositories.file_repository import FileRepository
from app.genagent.repositories.db_repository import DbRepository

logger = logging.getLogger(__name__)

class KnowledgeRepository:
    """Repository for managing Knowledge base items"""
    
    def __init__(self, storage_type: str = "file", file_path: str = "agents_config/knowledge_base.json", db_connection=None):
        """
        Initialize the knowledge repository
        
        Args:
            storage_type: Type of storage to use ('file' or 'db')
            file_path: Path to the JSON file for storage (if using file storage)
            db_connection: Database connection (if using database storage)
        """
        self.storage_type = storage_type
        self.model_class = KnowledgeItem
        
        # Create appropriate repository implementation
        if storage_type == "file":
            self.repository: BaseRepository[KnowledgeItem] = FileRepository(file_path, KnowledgeItem)
        elif storage_type == "db":
            self.repository = DbRepository(KnowledgeItem, db_connection)
        else:
            raise ValueError(f"Invalid storage type: {storage_type}. Must be 'file' or 'db'")
    
    async def get_all_items(self) -> List[KnowledgeItem]:
        """Get all knowledge base items"""
        return await self.repository.get_all()
    
    async def get_item_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get a specific knowledge base item by ID"""
        return await self.repository.get_by_id(item_id)
    
    async def get_items_by_ids(self, item_ids: List[str]) -> List[KnowledgeItem]:
        """Get multiple knowledge base items by their IDs"""
        return await self.repository.get_by_ids(item_ids)
    
    async def create_item(self, item: KnowledgeItem) -> Optional[KnowledgeItem]:
        """Create a new knowledge base item"""
        return await self.repository.create(item)
    
    async def update_item(self, item_id: str, item: KnowledgeItem) -> Optional[KnowledgeItem]:
        """Update an existing knowledge base item"""
        return await self.repository.update(item_id, item)
    
    async def delete_item(self, item_id: str) -> bool:
        """Delete a knowledge base item"""
        return await self.repository.delete(item_id) 