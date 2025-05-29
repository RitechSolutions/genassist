import json
import os
import logging
from typing import Generic, TypeVar, List, Optional, Any, Dict, Type
from pydantic import BaseModel

from app.genagent.repositories.base_repository import BaseRepository

T = TypeVar('T', bound=BaseModel)  # Generic type must be a Pydantic model

logger = logging.getLogger(__name__)

class FileRepository(BaseRepository[T]):
    """File-based repository implementation using JSON files for storage"""
    
    def __init__(self, file_path: str, model_class: Type[T]):
        """
        Initialize the file repository
        
        Args:
            file_path: Path to the JSON file for storage
            model_class: The Pydantic model class for data validation
        """
        self.file_path = file_path
        self.model_class = model_class
        
        # Create the file if it doesn't exist
        if not os.path.exists(self.file_path):
            self._write_data([])
    
    def _read_data(self) -> List[Dict[str, Any]]:
        """Read data from the JSON file"""
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Error reading data from {self.file_path}: {str(e)}")
            return []
    
    def _write_data(self, data: List[Dict[str, Any]]) -> bool:
        """Write data to the JSON file"""
        try:
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error writing data to {self.file_path}: {str(e)}")
            return False
    
    async def get_all(self) -> List[T]:
        """Get all items"""
        data = self._read_data()
        return [self.model_class(**item) for item in data]
    
    async def get_by_id(self, id: str) -> Optional[T]:
        """Get an item by ID"""
        data = self._read_data()
        for item in data:
            if item.get("id") == id:
                return self.model_class(**item)
        return None
    
    async def get_by_ids(self, ids: List[str]) -> List[T]:
        """Get multiple items by their IDs"""
        if not ids:
            return []
        
        data = self._read_data()
        results = []
        
        for item in data:
            if item.get("id") in ids:
                try:
                    model = self.model_class(**item)
                    results.append(model)
                except Exception as e:
                    logger.warning(f"Invalid item data for ID {item.get('id')}: {str(e)}")
        
        return results
    
    async def create(self, item: T) -> Optional[T]:
        """Create a new item"""
        try:
            data = self._read_data()
            
            # Check if item with this ID already exists
            item_dict = item.dict()
            item_id = item_dict.get("id")
            
            if not item_id:
                logger.error("Cannot create item without ID")
                return None
                
            for existing in data:
                if existing.get("id") == item_id:
                    logger.warning(f"Item with ID {item_id} already exists")
                    return None
            
            # Add the new item
            data.append(item_dict)
            
            # Write the updated data
            if self._write_data(data):
                return item
            return None
            
        except Exception as e:
            logger.error(f"Error creating item: {str(e)}")
            return None
    
    async def update(self, id: str, item: T) -> Optional[T]:
        """Update an existing item"""
        try:
            data = self._read_data()
            
            # Make a copy of the item to avoid modifying the original
            item_dict = item.model_dump()
            # Ensure the ID doesn't change
            item_dict["id"] = id
            
            # Find and update the item
            updated = False
            for i, existing in enumerate(data):
                if existing.get("id") == id:
                    data[i] = item_dict
                    updated = True
                    break
            
            if not updated:
                logger.warning(f"Item with ID {id} not found for update")
                return None
            
            # Write the updated data
            if self._write_data(data):
                return self.model_class(**item_dict)
            return None
            
        except Exception as e:
            logger.error(f"Error updating item: {str(e)}")
            return None
    
    async def delete(self, id: str) -> bool:
        """Delete an item by ID"""
        try:
            data = self._read_data()
            
            # Find and remove the item
            for i, existing in enumerate(data):
                if existing.get("id") == id:
                    data.pop(i)
                    return self._write_data(data)
            
            logger.warning(f"Item with ID {id} not found for deletion")
            return False
            
        except Exception as e:
            logger.error(f"Error deleting item: {str(e)}")
            return False 