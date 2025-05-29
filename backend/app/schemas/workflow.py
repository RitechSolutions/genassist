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


def get_base_workflow(self, name: str) -> WorkflowCreate:
    return WorkflowCreate(
        name=f"{name} Workflow",
        description=f"Default workflow for {name}",
        nodes=[{"id": "b517909e-5d23-4d95-84c3-e175fc36e5a9", "data": {"label": "Chat Input", "handlers": [{"id": "output", "type": "source", "compatibility": "text"}], "placeholder": "Type a message..."}, "type": "chatInputNode", "width": 300, "height": 93, "position": {"x": 81.65653220098523, "y": 253.38376194958948}, "selected": False, "positionAbsolute": {"x": 81.65653220098523, "y": 253.38376194958948}}, {"id": "a0277bf8-0a3a-4ab7-8040-5f0570311622", "data": {"label": "Chat Output", "handlers": [{"id": "input", "type": "target", "compatibility": "text"}], "messages": []}, "type": "chatOutputNode", "width": 300, "height": 93, "dragging": False, "position": {"x": 1421.283752237165, "y": 253.39783185667665}, "selected": False, "positionAbsolute": {"x": 1421.283752237165, "y": 253.39783185667665}}, {"id": "d04bff89-3be3-4804-a08c-f5bfd719fa17", "data": {"label": "Prompt Template", "handlers": [{"id": "output", "type": "source", "compatibility": "text"}, {"id": "input_user_query", "type": "target", "compatibility": "text"}], "template": "Please configure Agent Workflow before using it! \n\nYour query: {{user_query}}", "includeHistory": False}, "type": "promptNode", "width": 400, "height": 261, "dragging": False, "position": {"x": 682.6322125384895, "y": 171.07247471791806}, "selected": False, "positionAbsolute": {"x": 682.6322125384895, "y": 171.07247471791806}}],
        edges=[{"id": "reactflow__edge-b517909e-5d23-4d95-84c3-e175fc36e5a9output-d04bff89-3be3-4804-a08c-f5bfd719fa17input_user_query", "source": "b517909e-5d23-4d95-84c3-e175fc36e5a9", "target": "d04bff89-3be3-4804-a08c-f5bfd719fa17", "sourceHandle": "output", "targetHandle": "input_user_query"}, {"id": "reactflow__edge-d04bff89-3be3-4804-a08c-f5bfd719fa17output-a0277bf8-0a3a-4ab7-8040-5f0570311622input", "source": "d04bff89-3be3-4804-a08c-f5bfd719fa17", "target": "a0277bf8-0a3a-4ab7-8040-5f0570311622", "sourceHandle": "output", "targetHandle": "input"}],
        version="1.0"
    )