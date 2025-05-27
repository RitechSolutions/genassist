from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Any, Dict, Type

T = TypeVar('T')  # Generic type for the model

class BaseRepository(Generic[T], ABC):
    """Base repository interface defining common operations"""
    
    @abstractmethod
    async def get_all(self) -> List[T]:
        """Get all items"""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[T]:
        """Get an item by ID"""
        pass
    
    @abstractmethod
    async def get_by_ids(self, ids: List[str]) -> List[T]:
        """Get multiple items by their IDs"""
        pass
    
    @abstractmethod
    async def create(self, item: T) -> Optional[T]:
        """Create a new item"""
        pass
    
    @abstractmethod
    async def update(self, id: str, item: T) -> Optional[T]:
        """Update an existing item"""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete an item by ID"""
        pass 