from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ConversationMemory:
    """Class to maintain conversation history across workflow executions"""
    
    _instances: Dict[str, "ConversationMemory"] = {}
    
    @classmethod
    def get_instance(cls, thread_id: str) -> "ConversationMemory":
        """Get or create a conversation memory instance for a thread ID"""
        if thread_id not in cls._instances:
            cls._instances[thread_id] = ConversationMemory(thread_id)
        return cls._instances[thread_id]
    
    @classmethod
    def clear_all(cls) -> None:
        """Clear all conversation memories"""
        cls._instances.clear()
    
    def __init__(self, thread_id: str):
        """Initialize the conversation memory"""
        self.thread_id = thread_id
        self.messages = []
        self.metadata = {}
        self.created_at = datetime.now().isoformat()
        self.last_updated = self.created_at
        self.executions_count = 0
    
    def add_message(self, role: str, content: Any, message_type: str = "text") -> None:
        """Add a message to the conversation"""
        message = {
            "role": role,
            "content": content,
            "type": message_type,
            "timestamp": datetime.now().isoformat(),
            "execution_count": self.executions_count
        }
        self.messages.append(message)
        self.last_updated = message["timestamp"]
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation"""
        self.add_message("user", content)
    
    def add_assistant_message(self, content: Any) -> None:
        """Add an assistant message to the conversation"""
        self.add_message("assistant", content)
    
    def add_workflow_execution(self, input_message: str, output_result: Any) -> None:
        """Record a complete workflow execution with input and output"""
        self.executions_count += 1
        
        # Add user input
        self.add_user_message(input_message)
        
        # Add final result as assistant output
        if isinstance(output_result, dict) and "output" in output_result:
            output_content = output_result["output"]
        elif isinstance(output_result, dict) and "content" in output_result:
            output_content = output_result["content"]
        elif isinstance(output_result, list) and len(output_result) > 0:
            if isinstance(output_result[0], dict) and "content" in output_result[0]:
                output_content = output_result[0]["content"]
            else:
                output_content = str(output_result)
        else:
            output_content = str(output_result)
            
        self.add_assistant_message(output_content)
    
    def get_messages(self, max_messages: int = None, roles: List[str] = None) -> List[Dict[str, Any]]:
        """Get messages from the conversation, optionally filtered by role"""
        filtered = self.messages
        if roles:
            filtered = [m for m in filtered if m["role"] in roles]
        if max_messages:
            filtered = filtered[-max_messages:]
        return filtered
    
    def get_last_message(self, role: str = None) -> Optional[Dict[str, Any]]:
        """Get the last message, optionally filtered by role"""
        if not self.messages:
            return None
        
        if role:
            for message in reversed(self.messages):
                if message["role"] == role:
                    return message
            return None
        
        return self.messages[-1]
    
    def clear(self) -> None:
        """Clear the conversation"""
        self.messages = []
        self.last_updated = datetime.now().isoformat()
        self.executions_count = 0
    
    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata for the conversation"""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata for the conversation"""
        return self.metadata.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the conversation memory to a dictionary"""
        return {
            "thread_id": self.thread_id,
            "messages": self.messages,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "executions_count": self.executions_count
        }
    
    def get_chat_history(self, as_string: bool = False) -> Union[List[Dict[str, Any]], str]:
        """Get the chat history in a format suitable for LLM context"""
        if as_string:
            history_parts = []
            for message in self.messages:
                prefix = f"{message['role'].capitalize()}: "
                content = message["content"]
                history_parts.append(f"{prefix}{content}")
            return "\n".join(history_parts)
        
        return self.messages

