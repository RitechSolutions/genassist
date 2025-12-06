from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None
    testInput: Optional[dict] = None
    executionState: Optional[dict] = None

    user_id: Optional[UUID] = None
    version: str
    agent_id: Optional[UUID] = None


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None
    testInput: Optional[dict] = None
    executionState: Optional[dict] = None
    user_id: Optional[UUID] = None
    version: Optional[str] = None
    agent_id: Optional[UUID] = None


class WorkflowInDB(WorkflowBase):
    id: UUID
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Workflow(WorkflowInDB):
    pass


def get_base_workflow(name: str) -> WorkflowCreate:
    """
    Get the base workflow for an agent
    """
    return WorkflowCreate(
        name=f"{name} Workflow",
        description=f"Default workflow for {name}",
        nodes=[
            {
                "id": "b29e4ffa-3297-4803-9a2f-671cf5d4c257",
                "data": {
                    "name": "Start",
                    "label": "Start",
                    "handlers": [
                        {
                            "id": "output",
                            "type": "source",
                            "position": "right",
                            "compatibility": "any",
                        }
                    ],
                    "inputSchema": {
                        "message": {
                            "type": "string",
                            "required": True,
                            "description": "The input received from the user.",
                            "defaultValue": "",
                        }
                    },
                },
                "type": "chatInputNode",
                "width": 400,
                "height": 174,
                "dragging": False,
                "position": {"x": 76.85553797620844, "y": 144.20172491226504},
                "selected": False,
                "positionAbsolute": {"x": 76.85553797620844, "y": 144.20172491226504},
            },
            {
                "id": "b36544f8-5de2-44b6-80e2-26ddb99d9a61",
                "data": {
                    "name": "Finish",
                    "label": "Finish",
                    "handlers": [
                        {
                            "id": "input",
                            "type": "target",
                            "position": "left",
                            "compatibility": "any",
                        }
                    ],
                },
                "type": "chatOutputNode",
                "width": 400,
                "height": 120,
                "dragging": False,
                "position": {"x": 1130.4305699456777, "y": 170.34889110027814},
                "selected": False,
                "positionAbsolute": {"x": 1130.4305699456777, "y": 170.34889110027814},
            },
            {
                "id": "71489c81-e5ab-466d-a6ad-ae9bdadfe1c8",
                "data": {
                    "name": "Text Template",
                    "label": "Text Template",
                    "handlers": [
                        {
                            "id": "input",
                            "type": "target",
                            "position": "left",
                            "compatibility": "any",
                        },
                        {
                            "id": "output",
                            "type": "source",
                            "position": "right",
                            "compatibility": "any",
                        },
                    ],
                    "template": "This was the user's input: {{source.message}}",
                },
                "type": "templateNode",
                "width": 400,
                "height": 226,
                "dragging": False,
                "position": {"x": 609.6429982336459, "y": 117.71733785398649},
                "selected": False,
                "positionAbsolute": {"x": 609.6429982336459, "y": 117.71733785398649},
            },
        ],
        edges=[
            {
                "id": "reactflow__edge-b29e4ffa-3297-4803-9a2f-671cf5d4c257output-71489c81-e5ab-466d-a6ad-ae9bdadfe1c8input",
                "type": "default",
                "style": {"strokeWidth": 2, "stroke": "#64748b"},
                "source": "b29e4ffa-3297-4803-9a2f-671cf5d4c257",
                "target": "71489c81-e5ab-466d-a6ad-ae9bdadfe1c8",
                "markerEnd": {
                    "type": "arrowclosed",
                    "width": 20,
                    "height": 20,
                    "color": "#64748b",
                },
                "sourceHandle": "output",
                "targetHandle": "input",
            },
            {
                "id": "reactflow__edge-71489c81-e5ab-466d-a6ad-ae9bdadfe1c8output-b36544f8-5de2-44b6-80e2-26ddb99d9a61input",
                "type": "default",
                "style": {"strokeWidth": 2, "stroke": "#64748b"},
                "source": "71489c81-e5ab-466d-a6ad-ae9bdadfe1c8",
                "target": "b36544f8-5de2-44b6-80e2-26ddb99d9a61",
                "markerEnd": {
                    "type": "arrowclosed",
                    "width": 20,
                    "height": 20,
                    "color": "#64748b",
                },
                "sourceHandle": "output",
                "targetHandle": "input",
            },
        ],
        executionState={
            "source": {"message": "Hello!"},
            "session": {"message": "Hello!"},
            "nodeOutputs": {
                "b29e4ffa-3297-4803-9a2f-671cf5d4c257": {
                    "output": {"message": "Hello!"},
                    "status": "success",
                    "nodeName": "Start",
                    "nodeType": "chatInputNode",
                    "timestamp": 1763052821945,
                },
                "71489c81-e5ab-466d-a6ad-ae9bdadfe1c8": {
                    "output": "This was the user's input: Hello!",
                    "status": "success",
                    "nodeName": "Text Template",
                    "nodeType": "templateNode",
                    "timestamp": 1763052865514,
                },
                "b36544f8-5de2-44b6-80e2-26ddb99d9a61": {
                    "output": {},
                    "status": "success",
                    "nodeName": "Finish",
                    "nodeType": "chatOutputNode",
                    "timestamp": 1763052880098,
                },
            },
        },
        version="1.0",
    )
