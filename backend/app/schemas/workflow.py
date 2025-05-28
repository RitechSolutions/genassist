from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, validator
import json


class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None
    user_id: Optional[UUID] = None
    version: str
    
class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None
    version: Optional[str] = None


class WorkflowInDB(WorkflowBase):
    id: UUID
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes = True
    )


class Workflow(WorkflowInDB):
    pass 