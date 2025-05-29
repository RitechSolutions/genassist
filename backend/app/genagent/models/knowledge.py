from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class KnowledgeItem(BaseModel):
    """Knowledge base item model"""
    id: str
    name: str
    description: Optional[str] = None
    source: Optional[str] = None
    content: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    vector_store: Optional[str] = None
    embeddings_model: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"  # Allow additional fields for flexibility 