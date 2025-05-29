from typing import List, Optional
import logging

from app.genagent.models.knowledge import KnowledgeItem
from app.genagent.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)

class KnowledgeService:
    """Service for managing knowledge base items"""
    
    def __init__(
        self, 
        repository: Optional[KnowledgeRepository] = None,
    ):
        """Initialize the knowledge service with a repository and datasource_service"""
        # Create repository if not provided
        if repository is None:
            self.repository = KnowledgeRepository(
                storage_type="file",
            )
        else:
            self.repository = repository
    
    async def get_all_items(self) -> List[KnowledgeItem]:
        """Get all knowledge base items as KnowledgeItem objects"""
        try:
            return await self.repository.get_all_items()
        except Exception as e:
            logger.error(f"Error loading validated knowledge items: {str(e)}")
            return []
    

    async def get_item_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        """Get a specific knowledge base item by ID as a dictionary"""
        try:
            return await self.repository.get_item_by_id(item_id)
        except Exception as e:
            logger.error(f"Error getting validated knowledge item by ID: {str(e)}")
            return None
    

    async def get_items_by_ids(self, item_ids: List[str]) -> List[KnowledgeItem]:
        """Get multiple knowledge base items by their IDs as dictionaries"""
        if not item_ids:
            return []
        
        try:
            items = await self.repository.get_items_by_ids(item_ids)
            return items
        except Exception as e:
            logger.error(f"Error getting knowledge items by IDs: {str(e)}")
            return []
    
    async def create_item(self, knowledge_item: KnowledgeItem) -> Optional[KnowledgeItem]:
        """Create a new knowledge base item"""
        try:

            # Store in repository
            created_item = await self.repository.create_item(knowledge_item)
            
            return created_item
        except Exception as e:
            logger.error(f"Error creating knowledge base item: {str(e)}")
            return None
    
    async def update_item(self, item_id: str, knowledge_item: KnowledgeItem) -> Optional[KnowledgeItem]:
        """Update an existing knowledge base item"""
        logger.info(f"update_item: item_id = {item_id}")
        try:
            # Ensure the ID doesn't change
            knowledge_item.id = item_id
            updated_item = await self.repository.update_item(item_id, knowledge_item)
            return updated_item
        except Exception as e:
            logger.error(f"Error updating knowledge base item: {str(e)}")
            return None
    
    async def delete_item(self, item_id: str) -> bool:
        """Delete a knowledge base item"""
        try:
            # Delete from repository
            success = await self.repository.delete_item(item_id)
            return success
        except Exception as e:
            logger.error(f"Error deleting knowledge base item: {str(e)}")
            return False
    