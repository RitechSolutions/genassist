from abc import ABC, abstractmethod
from typing import Dict, List, Any

class DataSourceProvider(ABC):
    """Base abstract class for all data source providers"""
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the data source connection"""
        pass
    
    @abstractmethod
<<<<<<< HEAD
    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
=======
    async def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
>>>>>>> development
        """Add a document to the data source"""
        pass
    
    @abstractmethod
<<<<<<< HEAD
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the data source"""
        pass
=======
    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the data source"""
        pass

    @abstractmethod
    async def get_document_ids(self, kb_id: str) -> List[str]:
        """Get document IDs from the data source for the given knowledge base id"""
        pass
>>>>>>> development
    
    @abstractmethod
    async def search(self, query: str, limit: int = 5, doc_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Search the data source"""
        
        pass