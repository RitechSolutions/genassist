from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

class Position(BaseModel):
    x: float
    y: float

class Handler(BaseModel):
    id: str
    type: str = Field(..., pattern="^(source|target)$")
    compatibility: str = Field(..., pattern="^(text|json|tools|any)$")

class BaseNodeData(BaseModel):
    label: str
    handlers: List[Handler]

class ChatInputNodeData(BaseNodeData):
    placeholder: str = "Type a message..."

class ChatOutputNodeData(BaseNodeData):
    messages: List[Dict[str, str]] = []

class PromptNodeData(BaseNodeData):
    template: str
    inputValues: Dict[str, Any] = {}

class LLMModelNodeData(BaseNodeData):
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    apiKey: Optional[str] = None
    temperature: float = 0.7
    maxTokens: int = 1024

class ApiToolNodeData(BaseNodeData):
    name: str
    description: str
    endpoint: str
    method: str = "GET"
    headers: Dict[str, str] = {}
    parameters: Dict[str, Any] = {}
    requestBody: str = ""
    response: str = ""
    inputSchema: Dict[str, Dict[str, Any]] = {}
    outputSchema: Dict[str, Dict[str, Any]] = {}

class KnowledgeToolNodeData(BaseNodeData):
    name: str
    description: str
    selectedBases: List[str] = []
    query: str = ""
    inputSchema: Dict[str, Dict[str, Any]] = {}
    outputSchema: Dict[str, Dict[str, Any]] = {}

class AgentNodeData(BaseNodeData):
    name: str
    description: str
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    apiKey: Optional[str] = None
    temperature: float = 0.7
    maxTokens: int = 1024
    humanEnabled: bool = False
    inputSchema: Dict[str, Dict[str, Any]] = {}
    outputSchema: Dict[str, Dict[str, Any]] = {}

class Node(BaseModel):
    id: str
    type: str = Field(..., pattern="^(chatInputNode|chatOutputNode|promptNode|llmModelNode|apiToolNode|knowledgeToolNode|agentNode)$")
    position: Position
    data: Union[
        ChatInputNodeData,
        ChatOutputNodeData,
        PromptNodeData,
        LLMModelNodeData,
        ApiToolNodeData,
        KnowledgeToolNodeData,
        AgentNodeData
    ]
    width: int
    height: int

# Node type to data class mapping
NODE_TYPE_TO_DATA_CLASS = {
    "chatInputNode": ChatInputNodeData,
    "chatOutputNode": ChatOutputNodeData,
    "promptNode": PromptNodeData,
    "llmModelNode": LLMModelNodeData,
    "apiToolNode": ApiToolNodeData,
    "knowledgeToolNode": KnowledgeToolNodeData,
    "agentNode": AgentNodeData
}

def validate_node(node_data: Dict[str, Any]) -> Node:
    """Validate a node's data against its schema"""
    return Node(**node_data)

def get_node_data_class(node_type: str) -> type:
    """Get the appropriate data class for a node type"""
    return NODE_TYPE_TO_DATA_CLASS.get(node_type, BaseNodeData) 