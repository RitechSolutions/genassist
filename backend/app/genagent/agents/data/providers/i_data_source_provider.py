from abc import ABC, abstractmethod
from typing import Dict, List, Any

class DataSourceProvider(ABC):
    """Base abstract class for all data source providers"""
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the data source connection"""
        pass
    
    @abstractmethod
    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        """Add a document to the data source"""
        pass
    
    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the data source"""
        pass
    
    @abstractmethod
    async def search(self, query: str, limit: int = 5, doc_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Search the data source"""
        
        pass