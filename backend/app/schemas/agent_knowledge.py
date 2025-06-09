from uuid import UUID
from typing import Any, Dict, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class RagConfigRead(BaseModel):
    enabled: bool = True
    vector_db: Dict[str, Any] = Field(default_factory=dict)
    graph_db: Dict[str, Any] = Field(default_factory=dict)
    light_rag: Dict[str, Any] = Field(default_factory=dict)


class KBBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: Literal["file", "url", "text", "datasource","s3","database"]
    source: Optional[str] = None
    content: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    file: Optional[str] = None
    vector_store: Optional[Dict[str, Any]] = None
    rag_config: RagConfigRead = RagConfigRead()
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
    embeddings_model: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")

    last_synced: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    last_file_date: Optional[datetime] = None
    sync_schedule: Optional[str] = None
    sync_active: Optional[bool] = None
    sync_source_id: Optional[UUID] = None
    llm_provider_id: Optional[UUID] = None

class KBCreate(KBBase):
    """Body model for POST / PUT (no id)"""


class KBRead(KBBase):
    """Response model"""
    id: UUID
