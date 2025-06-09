from typing import Dict, Any, List, Optional
import logging
import uuid
from pydantic import BaseModel, ConfigDict

from app.modules.agents.workflow.base_processor import NodeProcessor

from app.modules.agents.workflow.nodes.agent import AgentNodeProcessor
from app.modules.agents.workflow.nodes.api_tool import ApiToolNodeProcessor
from app.modules.agents.workflow.nodes.chat import ChatInputNodeProcessor, ChatOutputNodeProcessor
from app.modules.agents.workflow.nodes.knowledge_tool import KnowledgeToolNodeProcessor
from app.modules.agents.workflow.nodes.llm_model import LLMModelNodeProcessor
from app.modules.agents.workflow.nodes.prompt import PromptNodeProcessor
from app.modules.agents.workflow.nodes.python_tool import PythonFunctionNodeProcessor

from app.modules.agents.workflow.nodes.slack_tool import SlackMessageNodeProcessor
from app.modules.agents.workflow.nodes.zendesk_tool import ZendeskTicketNodeProcessor


from app.modules.agents.workflow.state import WorkflowState
from app.schemas.workflow import Workflow

logger = logging.getLogger(__name__)

class WorkflowContext(BaseModel):
    """Context for workflow execution that holds state and references"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    nodes: Dict[str, Any]
    source_edges: Dict[str, Any]
    target_edges: Dict[str, Any]
    node_processors: Dict[str, NodeProcessor]
    state: Optional[WorkflowState]
    workflow_id: Optional[str]
    
    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by its ID"""
        return self.nodes.get(node_id)
    
    def get_source_edges(self, node_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get source edges for a node"""
        return self.source_edges.get(node_id, [])
    
    def get_target_edges(self, node_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get target edges for a node"""
        return self.target_edges.get(node_id, [])
    
    def get_node_processor(self, node_id: str) -> Optional[NodeProcessor]:
        """Get node processor for a node"""
        return self.node_processors.get(node_id)

    def get_nodes(self) -> Dict[str, Any]:
        """Get all nodes"""
        return self.nodes
    
    def get_all_source_edges(self) -> Dict[str, Any]:
        """Get all source edges"""
        return self.source_edges
    
    def get_all_target_edges(self) -> Dict[str, Any]:
        """Get all target edges"""
        return self.target_edges
    
    def get_all_node_processors(self) -> Dict[str, Any]:
        """Get all node processors"""
        return self.node_processors
    
    def get_node_processor(self, node_id: str) -> Optional[NodeProcessor]:
        """Get a node processor by ID"""
        return self.node_processors.get(node_id)
    
    def get_state(self) -> Optional[WorkflowState]:
        """Get the workflow state"""
        return self.state
    
    def get_workflow_id(self) -> str:
        """Get the workflow ID"""
        return self.workflow_id
    
class WorkflowBuilder:
    """Builder for creating executable workflows from ReactFlow configurations"""
    
    def __init__(self, workflow_model: Workflow = None):
        """Initialize the workflow builder"""
        self.workflow_model = workflow_model
        logger.info(f"Workflow model: : {self.workflow_model.__dict__}")
        self.workflow_id = workflow_model.id if workflow_model and hasattr(workflow_model, 'id') else None
        self.context = WorkflowContext(
            nodes={},
            source_edges={},
            target_edges={},
            node_processors={},
            state=None,
            workflow_id=str(self.workflow_id)
        )
        self._initialize()
    
    def _initialize(self):
        """Initialize the workflow from the configuration"""
        if not self.workflow_model:
            logger.error("No workflow configuration provided")
            return
        
        # Parse nodes and create a lookup by ID
        for node in self.workflow_model.nodes:
            node_id = node.get("id")
            if node_id:
                self.context.nodes[node_id] = node
                # processor = self._create_node_processor(node_id)
                # if not processor:
                #     logger.error(f"Could not create processor for node {node_id}")
                #     return
                # self.context.node_processors[node_id] = processor
        
        # Parse edges and group by source
        for edge in self.workflow_model.edges:
            source = edge.get("source")
            target = edge.get("target")
            if source:
                if source not in self.context.get_all_source_edges():
                    self.context.source_edges[source] = []
                self.context.source_edges[source].append(edge)
            if target:
                if target not in self.context.get_all_target_edges():
                    self.context.target_edges[target] = []
                self.context.target_edges[target].append(edge)
                

    def _create_node_processor(self, node_id: str) -> Optional[NodeProcessor]:
        """Create a processor for the given node ID"""
        if node_id not in self.context.nodes:
            logger.error(f"Node with ID {node_id} not found")
            return None
        
        node = self.context.get_node_by_id(node_id)
        node_type = node.get("type")
        node_data = node.get("data", {})
        
        # Create the appropriate processor based on node type
        processor = None

        if node_type == "chatInputNode":
            processor = ChatInputNodeProcessor(self.context, node_id, node_data)
        elif node_type == "promptNode":
            processor = PromptNodeProcessor(self.context, node_id, node_data)
        elif node_type == "llmModelNode":
            processor = LLMModelNodeProcessor(self.context, node_id, node_data)
        elif node_type == "chatOutputNode":
            processor = ChatOutputNodeProcessor(self.context, node_id, node_data)
        elif node_type == "apiToolNode":
            processor = ApiToolNodeProcessor(self.context, node_id, node_data)
        elif node_type == "knowledgeToolNode" or node_type == "knowledgeBaseNode":
            processor = KnowledgeToolNodeProcessor(self.context, node_id, node_data)
        elif node_type == "pythonCodeNode":
            processor = PythonFunctionNodeProcessor(self.context, node_id, node_data)
        elif node == "slackMessageNode":
            processor = SlackMessageNodeProcessor(self.context, node_id, node_data)
        elif node_type == "zendeskTicketNode":
            processor = ZendeskTicketNodeProcessor(self.context, node_id, node_data)
        elif node_type == "agentNode":
            processor = AgentNodeProcessor(self.context, node_id, node_data)
        else:
            logger.warning(f"Unsupported node type: {node_type}")
            return None
        return processor
    
    
    
    def _get_next_nodes(self, node_id: str) -> List[str]:
        """Get the IDs of nodes that follow the given node in the workflow"""
        next_nodes = []
        for edge in self.context.get_source_edges(node_id):
            target = edge.get("target")
            if target:
                next_nodes.append(target)
        return next_nodes
    
    def _get_start_node(self) -> str:
        for node_id, node in self.context.get_nodes().items():
            if node.get("type") == "chatInputNode" and node_id in self.context.source_edges and node_id not in self.context.target_edges:
                return node_id
        return None
    
    def _get_input_provider_nodes(self, node_id: str, visited: set) -> set:
        """Get all nodes that provide inputs to the given node"""
        if node_id in visited:
            return set()
        
        visited.add(node_id)
        input_providers = set()
        
        # Get all target edges (nodes that provide input to this node)
        for edge in self.context.get_target_edges(node_id):
            source = edge.get("source")
            target = edge.get("target")
            if source and "input_tools" not in target:
                input_providers.add(source)
                # Recursively get input providers for the source node
                input_providers.update(self._get_input_provider_nodes(source, visited))
        
        return input_providers
    
    
    def initialize_all_processors(self) -> None:
        """Initialize all processors"""
        for node_id in self.context.get_nodes():
            self.initialize_processor(node_id)
            
        logger.info(f"Initialized processors: {self.context.get_all_node_processors()}")
            
    def initialize_processor(self, node_id: str) -> None:
        """Initialize a processor for a node"""
        if node_id not in self.context.get_all_node_processors():
            processor = self._create_node_processor(node_id)
            if not processor:
                logger.error(f"Could not create processor for node {node_id}")
                return
            self.context.node_processors[node_id] = processor

    async def _execute_node_and_successors(self, node_id: str, visited: set) -> None:
        """Execute a node and all its successors in the workflow"""
        if node_id in visited:
            return
        
        visited.add(node_id)
        
        # # First, collect all nodes that need to be processed
        # all_nodes_to_process = set()
        # current_node = node_id
        
        # # Get all nodes in the forward path
        # while current_node:
        #     all_nodes_to_process.add(current_node)
        #     next_nodes = self._get_next_nodes(current_node)
        #     if next_nodes:
        #         current_node = next_nodes[0]  # Take the first next node
        #     else:
        #         current_node = None
        
        # # Get all input provider nodes for the collected nodes
        # input_providers = set()
        # for node in all_nodes_to_process:
        #     input_providers.update(self._get_input_provider_nodes(node, set()))
        
        # # Add input providers to the set of nodes to process
        # all_nodes_to_process.update(input_providers)
        
        # # Process all nodes in the correct order
        # for node_id in all_nodes_to_process:
        #     if node_id not in self.context.get_all_node_processors():
        #         processor = self._create_node_processor(node_id)
        #         if not processor:
        #             logger.error(f"Could not create processor for node {node_id}")
        #             continue
        #         self.context.node_processors[node_id] = processor
            
        #     await self.context.get_node_processor(node_id).process()
        
        # self.initialize_processor(node_id)
        await self.context.get_node_processor(node_id).process()
        
        next_nodes = self._get_next_nodes(node_id)
        for next_node_id in next_nodes:
            await self._execute_node_and_successors(next_node_id, visited)

    
    async def execute(self, user_query: str = None, start_node_id: str = None, metadata: dict = None) -> Dict[str, Any]:
        """Execute the workflow with the given input message"""
        thread_id = metadata.get("thread_id", str(uuid.uuid4()))

        # if metadata is None or metadata.get("thread_id") is None:
        #     raise ValueError("Thread ID is required in metadata")
            
        self.context.state = WorkflowState(thread_id=thread_id, input=user_query, metadata=metadata)
        self.context.state.get_memory().add_user_message(user_query)
        
        if not start_node_id:
            start_node_id = self._get_start_node()
            if not start_node_id:
                return {"status": "error", "message": "No starting nodes found"}
        
        self.context.node_processors = {}
        self.initialize_all_processors()
        visited = set()
        await self._execute_node_and_successors(start_node_id, visited)
        
        node_results = []
        output_node_types = ["chatOutputNode"]
        output_message = None
        
        for node_id, node in self.context.get_nodes().items():
            if node_id in self.context.get_all_node_processors():
                processor = self.context.get_node_processor(node_id)
                node_results.append({
                    "node_id": node_id,
                    "type": node.get("type"),
                    "input": processor.get_input(),
                    "output": processor.get_output()
                })
                if node.get("type") in output_node_types:
                    output_message = processor.get_output()
        
        if output_message:
            self.context.state.get_memory().add_assistant_message(output_message)
        
        return {
            "status": "success",
            "input": user_query,
            "output": output_message,
            "workflow_id": str(self.workflow_model.id) if hasattr(self.workflow_model, 'id') else None,
            "execution_summary": self.context.state.get_execution_summary()
        }
