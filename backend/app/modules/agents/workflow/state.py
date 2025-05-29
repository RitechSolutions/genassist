from typing import Dict, Any, List, Optional, Callable, Union
import logging
import uuid

from datetime import datetime

from app.modules.agents.workflow.memory import ConversationMemory


logger = logging.getLogger(__name__)

class WorkflowState:
    """Class to maintain state during workflow execution"""
    
    def __init__(self, thread_id:str = str(uuid.uuid4()), input: Any = None, metadata: dict = None):
        """Initialize the workflow state"""
        self.thread_id = thread_id
        self.input = input
        self.user_query = input if isinstance(input, str) else ""
        self.timestamp = datetime.now().isoformat()
        self.execution_id = str(uuid.uuid4())
        self.memory = ConversationMemory.get_instance(thread_id=self.thread_id)
        self.metadata = metadata
        
        self.node_outputs = {}
        self.node_inputs = {}
        self.edge_data = {}
        self.execution_path = []
        self.output = None
        # Initialize conversation memory
        
        
    def get_user_query(self) -> str:
        """Get the user query from the global context"""
        return self.user_query
    
    def get_thread_id(self) -> str:
        """Get the thread ID for this workflow execution"""
        return self.thread_id
    
    def get_session_metadata(self) -> dict:
        """Get the metadata for this workflow execution"""
        return self.metadata if self.metadata else {}
    
    def get_memory(self) -> ConversationMemory:
        """Get the conversation memory for this workflow execution"""
        return self.memory
    
    def record_workflow_output(self, output: Any) -> None:
        """Record the final output of the workflow execution"""
        self.output = output
    
    def get_workflow_output(self) -> Any:
        """Get the final output of the workflow execution"""
        return self.output
    

    def get_node_output(self, node_id: str) -> Any:
        """Get the output of a specific node"""
        return self.node_outputs.get(node_id)
    
    def set_node_output(self, node_id: str, output: Any) -> None:
        """Set the output of a specific node"""
        self.node_outputs[node_id] = output
        if node_id not in self.execution_path:
            self.execution_path.append(f"{node_id}")

    def set_node_input(self, node_id: str, input_data: Any) -> None:
        """Set the input for a specific node"""
        self.node_inputs[node_id] = input_data
    
    def get_node_input(self, node_id: str) -> Any:
        """Get the input for a specific node"""
        return self.node_inputs.get(node_id)
    
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the workflow execution"""
        return {
            "execution_id": self.execution_id,
            "thread_id": self.thread_id,
            "timestamp": self.timestamp,
            "execution_path": self.execution_path,
            "input": self.input,
            "node_outputs": self.node_outputs,
        }

