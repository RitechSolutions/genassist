import asyncio
from typing import Callable, Dict, Any, List, Optional
import logging


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.modules.agents.workflow.builder import  WorkflowContext
    
from app.modules.agents.utils import map_tool_to_schema
from app.modules.agents.workflow.memory import ConversationMemory

logger = logging.getLogger(__name__)

class NodeProcessor:
    """Base class for processing different node types in a workflow"""
    
    def __init__(self, context: 'WorkflowContext', node_id: str, node_data: Dict[str, Any]):
        self.node_id = node_id
        self.node_data = node_data
        self.output = None
        self.input = None
        self.context = context
        logger.info(f"Node initialized: {node_id} :{node_data.get('id')} : {node_data.get('type')}")
    
    def get_node_config(self) -> Dict[str, Any]:
        """Get the node config for this node"""
        return self.node_data if self.node_data else {}
    
    def get_target_handlers(self) -> List[Dict[str, Any]]:
        """Get the target handlers for this node"""
        handlers = self.node_data.get("handlers")
        return [h for h in handlers if h.get("type") == "target"]
    
    
    

    async def get_process_input(self, direct_input: Any = None, field_name: Optional[str] = "input") -> Any:
        """Get the input data for this node"""
        # This is the new method that doesn't take input_data as a parameter
        
        input_edges = await self.get_inputs_from_source_nodes()
        logger.info(f"Input edges: {input_edges}")
        target_handlers = self.get_target_handlers().copy()
        target_handlers = [h for h in target_handlers if field_name in h.get("id")]
        logger.info(f"Target handlers: {target_handlers}")
        logger.info(f"Input direct_input: {direct_input}")
        if not input_edges or len(input_edges) == 0:
            return direct_input if direct_input else {}
        
        for handler in target_handlers:
            handler["edges"] = [e for e in input_edges if e.get("target_handle") == handler.get("id")]
        

        result = {}

        for handler in target_handlers:
            if handler.get("compatibility") == "text":
                key = handler.get("id")
                result[key] = " ".join([e.get("data") for e in handler.get("edges")])
            elif handler.get("compatibility") == "tools":
                key = handler.get("id")
                result[key] = []
                for e in handler.get("edges"):
                    node = self.get_context().get_node_by_id(e.get("source_node_id"))
                    
                    result[key].append(map_tool_to_schema(node))
            else:
                raise ValueError("Tools are not supported yet")
        
        else:
            pass
        logger.info(f"Result edges: {result}")
        final_result = {}
        
        for key, value in result.items():
            if "_" not in key:
                final_result = value
            else:
                rem_key = key.replace("input_", "")
                final_result[rem_key] = value
        return final_result
        
        
  

        
    
    async def process(self, input_data: Any = None) -> Any:
        """Process the node using inputs from connected edges"""
        # This is the new method that doesn't take input_data as a parameter
        # Subclasses should override this method
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_output(self) -> Any:
        """Get the output from this node"""
        return self.output
    
    def get_input(self) -> Any:
        """Get the input for this node"""
        return self.input
    

    def get_state(self):
        """Get the state for this node"""
        return self.context.state if self.context else None
    
    def get_context(self):
        """Get the context for this node"""
        return self.context
    
    def get_workflow(self):
        """Get the workflow for this node"""
        return self.context.workflow
    
    async def get_inputs_from_source_nodes(self, no_need_output: bool = True) -> List[Any]:
        """Get inputs from all incoming edges"""
        
        inputs = []
        try:
            edges = self.get_context().get_target_edges(self.node_id)
            logger.info(f"Edges: {edges}")
            # Get all edges that target this node
            if edges:
                for edge in edges:
                    source_id = edge.get("source")
                    logger.info(f"Source id: {source_id}")
                    source_output = self.get_context().state.get_node_output(source_id)
                    try:
                        logger.info(f"Source output: {source_output}")
                        node_processor = self.get_context().get_node_processor(source_id)
                        target_handlers = node_processor.get_target_handlers()
                        if target_handlers and len(target_handlers) > 0:
                            logger.info(f"Target handlers: {node_processor.get_node_config()}")
                            raise ValueError("Not runnable without input")
                   
                        await node_processor.process()
                        source_output = node_processor.get_output()
                    except Exception as e:
                        logger.error(f"Error getting source output: {e}")
                    if source_output is not None or no_need_output:
                        # Check if there's a specific handle mapping
                        target_handle = edge.get("targetHandle")
                        source_handle = edge.get("sourceHandle")
                        
                        # Store input with metadata about the connection
                        input_with_metadata = {
                            "data": source_output if source_output is not None else "",
                            "source_node_id": source_id,
                            "source_handle": source_handle,
                            "target_handle": target_handle,
                            "edge_id": edge.get("id")
                        }
                        logger.info(f"Input with metadata: {input_with_metadata}")

                        inputs.append(input_with_metadata)
        except Exception as e:
            logger.error(f"Error getting inputs from source nodes: {e}")
            return []
        return inputs
    
    def get_inputs_as_dict(self) -> Dict[str, Any]:
        """Get inputs from all incoming edges as a dictionary"""
        inputs = self.get_inputs_from_source_nodes()
        merged_dict = {}
        for input in inputs:
            if isinstance(input.get("data"), dict):
                merged_dict.update(input.get("data"))
            elif isinstance(input.get("data"), list):
                merged_dict["output"]=input.get("data")
            elif isinstance(input.get("data"), str):
                merged_dict["output"]=input.get("data")
        return merged_dict 
    
    def save_output(self, output: Any) -> None:
        """Save the output of this node"""
        self.output = output
        try:
            self.get_context().state.set_node_output(self.node_id, output)
        except Exception as e:
            logger.error(f"Error setting node output: {e}")
    
    def set_input(self, input: Any) -> None:
        """Set the input for this node"""
        self.input = input
        try:
            self.get_context().state.set_node_input(self.node_id, input)
        except Exception as e:
            logger.error(f"Error setting node input: {e}")
    
    def get_memory(self) -> ConversationMemory:
        """Get the conversation memory for this workflow"""
        try:
            return self.get_context().state.get_memory()
        except Exception as e:
            logger.error(f"Error getting memory: {e}")
            return None
    

