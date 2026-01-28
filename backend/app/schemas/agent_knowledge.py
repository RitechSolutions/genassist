from uuid import UUID
from typing import Any, Dict, Optional, Literal, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator


class KBBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: Literal["file", "url", "text", "datasource",
                  "s3", "database", "sharepoint", "smb_share_folder", "azure_blob", "google_bucket", "zendesk"] = "file"
    source: Optional[str] = None
    content: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    files: Optional[List[str]] = None
    vector_store: Optional[Dict[str, Any]] = None
    rag_config: Optional[Dict[str, Any]] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
    embeddings_model: Optional[str] = None
    legra_finalize: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True, extra="allow")

    @model_validator(mode='after')
    def validate_rag_config(self) -> 'KBBase':
        """Validate rag_config structure and embedding model names"""
        if not self.rag_config:
            return self

        # Import here to avoid circular dependency
        from app.constants.embedding_models import ALLOWED_MODEL_NAMES, MODELS_FOR_DOWNLOAD

        # Validate vector config embedding model
        if vector_config := self.rag_config.get('vector'):
            if vector_config.get('enabled') and (model := vector_config.get('embedding_model_name')):
                if model not in ALLOWED_MODEL_NAMES:
                    raise ValueError(
                        f'Invalid embedding_model_name: "{model}". '
                        f'Must be one of: {", ".join(ALLOWED_MODEL_NAMES)}'
                    )

        # Validate LEGRA config embedding model
        if legra_config := self.rag_config.get('legra'):
            if legra_config.get('enabled') and (model := legra_config.get('embedding_model')):
                # LEGRA uses full paths like 'sentence-transformers/all-MiniLM-L6-v2'
                if model not in MODELS_FOR_DOWNLOAD:
                    # Try stripping the prefix to give a better error message
                    model_name = model.replace('sentence-transformers/', '')
                    if model_name in ALLOWED_MODEL_NAMES:
                        raise ValueError(
                            f'Invalid embedding_model: "{model}". '
                            f'LEGRA requires the full path: "sentence-transformers/{model_name}"'
                        )
                    else:
                        raise ValueError(
                            f'Invalid embedding_model: "{model}". '
                            f'Must be one of: {", ".join(MODELS_FOR_DOWNLOAD)}'
                        )

        return self

    last_synced: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    last_file_date: Optional[datetime] = None
    sync_schedule: Optional[str] = None
    sync_active: Optional[bool] = None
    sync_source_id: Optional[UUID] = None
    llm_provider_id: Optional[UUID] = None
    urls: Optional[List[str]] = None


class KBCreate(KBBase):
    """Body model for POST / PUT (no id)"""


class KBRead(KBBase):
    """Response model"""
    id: UUID
