"""
Workflow engine for building and executing workflows with state management.
"""

from app.modules.workflow.utils import process_path_based_input_data
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.modules.workflow.engine.nodes import (
    ChatInputNode,
    ChatOutputNode,
    RouterNode,
    AgentNode,
    ApiToolNode,
    TemplateNode,
    LLMModelNode,
    KnowledgeToolNode,
    PythonToolNode,
    DataMapperNode,
    ToolBuilderNode,
    SlackToolNode,
    CalendarEventsNode,
    ReadMailsToolNode,
    GmailToolNode,
    WhatsAppToolNode,
    ZendeskToolNode,
    SQLNode,
    AggregatorNode,
    JiraNode,
    MLModelInferenceNode,
    TrainDataSourceNode,
    TrainPreprocessNode,
    TrainModelNode,
    ThreadRAGNode,
)
from typing import Dict, Any, List, Optional, Set
import logging
import asyncio
from collections import defaultdict
import uuid


logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Engine for building and executing workflows.

    Features:
    - Build workflows from configuration
    - Execute workflows with state tracking
    - Handle special nodes (router, aggregator)
    - Execute from specific starting nodes
    - Parallel execution support
    """

    _instances: Dict[str, "WorkflowEngine"] = {}

    @classmethod
    def get_instance(cls, workflow_id: str = str(uuid.uuid4())) -> "WorkflowEngine":
        """Get or create a workflow engine instance for a workflow ID"""
        if workflow_id not in cls._instances:
            logger.info(
                f"Creating new workflow engine instance for workflow ID: {workflow_id}"
            )
            cls._instances[workflow_id] = WorkflowEngine()
        return cls._instances[workflow_id]

    def initialize_workflow_engine(self):
        """
        Initialize the workflow engine.
        """
        self.node_registry: Dict[str, type] = {}
        self.workflows: Dict[str, Dict[str, Any]] = {}
        # Initialize the new workflow engine

        self.register_node_type("chatInputNode", ChatInputNode)
        self.register_node_type("chatOutputNode", ChatOutputNode)
        self.register_node_type("routerNode", RouterNode)
        self.register_node_type("agentNode", AgentNode)
        self.register_node_type("apiToolNode", ApiToolNode)
        self.register_node_type("templateNode", TemplateNode)
        self.register_node_type("llmModelNode", LLMModelNode)
        self.register_node_type("knowledgeBaseNode", KnowledgeToolNode)
        self.register_node_type("pythonCodeNode", PythonToolNode)
        self.register_node_type("dataMapperNode", DataMapperNode)
        self.register_node_type("toolBuilderNode", ToolBuilderNode)
        self.register_node_type("slackMessageNode", SlackToolNode)
        self.register_node_type("calendarEventNode", CalendarEventsNode)
        self.register_node_type("readMailsNode", ReadMailsToolNode)
        self.register_node_type("gmailNode", GmailToolNode)
        self.register_node_type("whatsappToolNode", WhatsAppToolNode)
        self.register_node_type("zendeskTicketNode", ZendeskToolNode)
        self.register_node_type("sqlNode", SQLNode)
        self.register_node_type("aggregatorNode", AggregatorNode)
        self.register_node_type("jiraNode", JiraNode)
        self.register_node_type("mlModelInferenceNode", MLModelInferenceNode)
        self.register_node_type("trainDataSourceNode", TrainDataSourceNode)
        self.register_node_type("preprocessingNode", TrainPreprocessNode)
        self.register_node_type("trainModelNode", TrainModelNode)
        self.register_node_type("threadRAGNode", ThreadRAGNode)

    def __init__(self):
        """Initialize the workflow engine."""
        self.initialize_workflow_engine()

    def register_node_type(self, node_type: str, node_class: type) -> None:
        """
        Register a node type with its implementation class.

        Args:
            node_type: The type identifier for the node
            node_class: The class that implements the node
        """
        if not issubclass(node_class, BaseNode):
            raise ValueError(f"Node class must inherit from BaseNode: {node_class}")

        self.node_registry[node_type] = node_class
        logger.info(f"Registered node type: {node_type} -> {node_class.__name__}")

    def build_workflow(self, workflow_config: Dict[str, Any]) -> str:
        """
        Build a workflow from configuration.

        Args:
            workflow_config: Workflow configuration dictionary

        Returns:
            Workflow ID
        """
        workflow_id = workflow_config.get("id", str(uuid.uuid4()))

        # Validate workflow structure
        if "nodes" not in workflow_config:
            raise ValueError("Workflow must contain nodes")

        # Store workflow configuration
        self.workflows[workflow_id] = {
            "config": workflow_config,
            "nodes": workflow_config["nodes"],
            "edges": workflow_config.get("edges", []),
            "metadata": {
                "name": workflow_config.get("name", "Unnamed Workflow"),
                "description": workflow_config.get("description", ""),
                "version": workflow_config.get("version", "1.0"),
                "created_at": workflow_config.get("created_at"),
                "updated_at": workflow_config.get("updated_at"),
            },
        }

        # Build edge mappings for efficient lookup
        self._build_edge_mappings(workflow_id)

        logger.info(
            f"Built workflow: {workflow_id} ({self.workflows[workflow_id]['metadata']['name']})"
        )
        return workflow_id

    def _build_edge_mappings(self, workflow_id: str) -> None:
        """Build efficient edge mappings for the workflow."""
        workflow = self.workflows[workflow_id]
        edges = workflow["edges"]

        # Source edges: node_id -> list of outgoing edges
        source_edges = defaultdict(list)
        # Target edges: node_id -> list of incoming edges
        target_edges = defaultdict(list)

        for edge in edges:
            source_id = edge["source"]
            target_id = edge["target"]

            source_edges[source_id].append(edge)
            target_edges[target_id].append(edge)

        workflow["source_edges"] = dict(source_edges)
        workflow["target_edges"] = dict(target_edges)

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow by ID."""
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> List[str]:
        """List all workflow IDs."""
        return list(self.workflows.keys())

    async def execute_from_node(
        self,
        workflow_id: str,
        start_node_id: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        thread_id: str = str(uuid.uuid4()),
    ) -> WorkflowState:
        """
        Execute workflow starting from a specific node.

        Args:
            workflow_id: ID of the workflow to execute
            start_node_id: Optional ID of the starting node
            input_data: Input data for the workflow
            thread_id: Thread ID for this execution

        Returns:
            WorkflowState with execution results
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        if not input_data:
            input_data = {}
            logger.warning("Input data is empty, using empty input data")

        if not start_node_id:

            start_node_ids = self._find_starting_nodes(workflow_id)
            if len(start_node_ids) == 1:
                start_node_id = start_node_ids[0]
            else:
                raise ValueError(f"Multiple starting nodes found: {start_node_ids}")

        # Verify start node exists
        if start_node_id not in [node["id"] for node in workflow["nodes"]]:
            raise ValueError(f"Start node not found: {start_node_id}")

        initial_values = process_path_based_input_data(input_data)

        # Create execution state
        state = WorkflowState(
            workflow=workflow,
            thread_id=thread_id or str(uuid.uuid4()),
            initial_values=initial_values,
        )

        try:
            state.start_execution()
            state.total_steps = len(workflow["nodes"])

            # Execute from the specified node
            try:
                await self._execute_from_node_recursive(
                    start_node_id, state, workflow_id, set()
                )

                state.complete_execution()
            except ValueError as e:
                state.fail_execution(str(e))

        except Exception as e:
            state.fail_execution(str(e))
            raise

        try:
            if initial_values.get("message"):
                asyncio.create_task(
                    state.get_memory().add_user_message(
                        initial_values.get("message", "")
                    )
                )
                asyncio.create_task(
                    state.get_memory().add_assistant_message(state.output)
                )

        except Exception as e:
            logger.error(f"Error adding message to memory: {e}")
        return state

    def _find_starting_nodes(self, workflow_id: str) -> List[str]:
        """Find nodes with no incoming edges (starting nodes)."""
        workflow = self.workflows[workflow_id]
        target_edges = workflow["target_edges"]

        input_node = None
        for node in workflow["nodes"]:
            if "input" in node["type"].lower():
                input_node = node
                break

        if input_node:
            return [input_node["id"]]

        starting_nodes = []
        for node in workflow["nodes"]:
            node_id = node["id"]
            if node_id not in target_edges or not target_edges[node_id]:
                starting_nodes.append(node_id)

        return starting_nodes

    async def _execute_from_node_recursive(
        self, node_id: str, state: WorkflowState, workflow_id: str, visited: Set[str]
    ) -> None:
        """Recursively execute nodes starting from a specific node."""
        if node_id in visited:
            return  # Avoid cycles

        visited.add(node_id)

        # _, node_type = self.get_node_config(workflow_id, node_id=node_id)

        node_output: Optional[dict] = None

        # if "aggregator" in node_type.lower():
        # Check if aggregator requirements are satisfied
        node = self.executable_node(node_id, state, workflow_id)
        executable_node = node.check_if_requirement_satisfied()
        if executable_node:
            # All sources are ready, execute the aggregator
            node_output = await self._execute_single_node(node_id, state, workflow_id)
        else:
            # Requirements not satisfied, skip execution and continue flow
            logger.debug(
                f"Aggregator {node_id} requirements not satisfied, skipping execution"
            )
            return
        # else:
        #     # Execute regular nodes normally
        #     node_output = await self._execute_single_node(node_id, state, workflow_id)

        # Handle next nodes based on execution result
        if node_output and "next_nodes" in node_output:
            next_nodes = node_output.get("next_nodes", [])
        else:
            next_nodes = self._find_next_nodes(node_id, workflow_id)

        # Find and execute next nodes in parallel
        if next_nodes:
            # Create tasks for all next nodes
            next_tasks = []
            for next_node_id in next_nodes:
                # Create a copy of visited set for each task to avoid conflicts
                task_visited = visited.copy()
                task = asyncio.create_task(
                    self._execute_from_node_recursive(
                        next_node_id, state, workflow_id, task_visited
                    )
                )
                next_tasks.append(task)

            # Execute all next nodes in parallel
            # Use return_exceptions=True to handle any individual task failures gracefully
            results = await asyncio.gather(*next_tasks, return_exceptions=True)

            # Log any exceptions that occurred during parallel execution
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Error in parallel execution of node {next_nodes[i]}: {result}"
                    )

    def _find_next_nodes(self, node_id: str, workflow_id: str) -> List[str]:
        """Find next nodes connected to the current node."""
        workflow = self.workflows[workflow_id]
        source_edges = workflow["source_edges"]

        next_nodes = []
        for edge in source_edges.get(node_id, []):
            next_nodes.append(edge["target"])

        return next_nodes

    def get_node_config(self, workflow_id: str, node_id: str):
        """Get the node config and type."""
        workflow = self.workflows[workflow_id]
        node_config = next(node for node in workflow["nodes"] if node["id"] == node_id)
        node_type = node_config.get("type", "")
        return node_config, node_type

    def executable_node(
        self, node_id: str, state: WorkflowState, workflow_id: str
    ) -> BaseNode:
        """Executable node."""
        node_config, node_type = self.get_node_config(
            workflow_id=workflow_id, node_id=node_id
        )
        node_class = self.node_registry.get(node_type)
        if not node_class:
            raise ValueError(f"Unknown node type: {node_type}, skipping node {node_id}")
        node = node_class(node_id, node_config, state)
        return node

    async def _execute_single_node(
        self, node_id: str, state: WorkflowState, workflow_id: str
    ) -> Any:

        try:
            node = self.executable_node(node_id, state, workflow_id)
            # Execute the node
            output = await node.execute()

            state.current_step += 1
            return output

        except Exception as e:
            logger.error(f"Error executing node {node_id}: {e}")
            state.fail_execution(f"Node {node_id} failed: {str(e)}")
            raise

    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the current status of a workflow."""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return {"error": "Workflow not found"}

        return {
            "workflow_id": workflow_id,
            "metadata": workflow["metadata"],
            "node_count": len(workflow["nodes"]),
            "edge_count": len(workflow["edges"]),
            "registered": True,
        }
