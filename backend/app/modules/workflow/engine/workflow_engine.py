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
    OpenAPINode,
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
    MCPNode,
    WorkflowExecutorNode,
)
from typing import Dict, Any, List, Optional, Set
import logging
import asyncio
from collections import defaultdict
import uuid
from fastapi_injector import RequestScopeFactory
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies.injector import injector
from app.core.tenant_scope import get_tenant_context, set_tenant_context


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

    # Class-level node registry - initialized once when module loads
    _node_registry: Dict[str, type] = {}
    _registry_initialized = False

    @classmethod
    def _initialize_node_registry(cls):
        """Initialize the node type registry (called once at class level)."""
        if cls._registry_initialized:
            return

        cls._node_registry["chatInputNode"] = ChatInputNode
        cls._node_registry["chatOutputNode"] = ChatOutputNode
        cls._node_registry["routerNode"] = RouterNode
        cls._node_registry["agentNode"] = AgentNode
        cls._node_registry["apiToolNode"] = ApiToolNode
        cls._node_registry["openApiNode"] = OpenAPINode
        cls._node_registry["templateNode"] = TemplateNode
        cls._node_registry["llmModelNode"] = LLMModelNode
        cls._node_registry["knowledgeBaseNode"] = KnowledgeToolNode
        cls._node_registry["pythonCodeNode"] = PythonToolNode
        cls._node_registry["dataMapperNode"] = DataMapperNode
        cls._node_registry["toolBuilderNode"] = ToolBuilderNode
        cls._node_registry["slackMessageNode"] = SlackToolNode
        cls._node_registry["calendarEventNode"] = CalendarEventsNode
        cls._node_registry["readMailsNode"] = ReadMailsToolNode
        cls._node_registry["gmailNode"] = GmailToolNode
        cls._node_registry["whatsappToolNode"] = WhatsAppToolNode
        cls._node_registry["zendeskTicketNode"] = ZendeskToolNode
        cls._node_registry["sqlNode"] = SQLNode
        cls._node_registry["aggregatorNode"] = AggregatorNode
        cls._node_registry["jiraNode"] = JiraNode
        cls._node_registry["mlModelInferenceNode"] = MLModelInferenceNode
        cls._node_registry["trainDataSourceNode"] = TrainDataSourceNode
        cls._node_registry["preprocessingNode"] = TrainPreprocessNode
        cls._node_registry["trainModelNode"] = TrainModelNode
        cls._node_registry["threadRAGNode"] = ThreadRAGNode
        cls._node_registry["mcpNode"] = MCPNode
        cls._node_registry["workflowExecutorNode"] = WorkflowExecutorNode

        cls._registry_initialized = True
        logger.debug(f"Initialized node registry with {len(cls._node_registry)} node types")

    def _node_needs_db_access(self, node_type: str) -> bool:
        """
        Determine if a node type requires database access.
        
        This helps optimize connection pool usage by only creating DB connections
        for nodes that actually need them.
        
        Args:
            node_type: The type identifier of the node
            
        Returns:
            True if the node needs DB access, False otherwise
        """
        # Node types that do NOT require database access
        # All other nodes are assumed to need DB access
        no_db_nodes = {
            "templateNode",
            "routerNode",
            "chatInputNode",
            "chatOutputNode",
            "pythonCodeNode",
            "apiToolNode",
            "dataMapperNode",
            "toolBuilderNode",
            "aggregatorNode",
        }
        
        # Return True if node is NOT in the no-DB list (i.e., it needs DB)
        return node_type not in no_db_nodes
    
    def __init__(self, workflow_config: Dict[str, Any]):
        """
        Initialize the workflow engine with a workflow configuration.

        Args:
            workflow_config: Workflow configuration dictionary with 'nodes' and optional 'edges'
        
        Raises:
            ValueError: If workflow_config is missing required fields
        """
        # Initialize the class-level node registry if not already done
        self.__class__._initialize_node_registry()
        
        # Validate workflow structure
        if not workflow_config:
            raise ValueError("workflow_config is required")
        if "nodes" not in workflow_config:
            raise ValueError("Workflow must contain nodes")

        # Store workflow ID
        self.workflow_id = workflow_config.get("id", str(uuid.uuid4()))

        # Build and store workflow configuration
        self.workflow = {
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
        self._build_edge_mappings()

        logger.info(
            f"Initialized workflow engine for workflow: {self.workflow_id} ({self.workflow['metadata']['name']})"
        )

    def _build_edge_mappings(self) -> None:
        """Build efficient edge mappings for the workflow."""
        edges = self.workflow["edges"]

        # Source edges: node_id -> list of outgoing edges
        source_edges = defaultdict(list)
        # Target edges: node_id -> list of incoming edges
        target_edges = defaultdict(list)

        for edge in edges:
            source_id = edge["source"]
            target_id = edge["target"]

            source_edges[source_id].append(edge)
            target_edges[target_id].append(edge)

        self.workflow["source_edges"] = dict(source_edges)
        self.workflow["target_edges"] = dict(target_edges)

    def get_workflow(self) -> Dict[str, Any]:
        """Get the workflow configuration."""
        return self.workflow

    async def execute_from_node(
        self,
        start_node_id: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        thread_id: str = str(uuid.uuid4()),
        persist: Optional[bool] = True,
    ) -> WorkflowState:
        """
        Execute workflow starting from a specific node.

        Args:
            start_node_id: Optional ID of the starting node
            input_data: Input data for the workflow
            thread_id: Thread ID for this execution
            persist: Whether to persist conversation to memory

        Returns:
            WorkflowState with execution results
        """
        if not input_data:
            input_data = {}
            logger.warning("Input data is empty, using empty input data")

        if not start_node_id:
            start_node_ids = self._find_starting_nodes()
            if len(start_node_ids) == 1:
                start_node_id = start_node_ids[0]
            else:
                raise ValueError(
                    f"Multiple starting nodes found: {start_node_ids}")

        # Verify start node exists
        if start_node_id not in [node["id"] for node in self.workflow["nodes"]]:
            raise ValueError(f"Start node not found: {start_node_id}")

        initial_values = process_path_based_input_data(input_data)

        # Create execution state
        state = WorkflowState(
            workflow=self.workflow,
            thread_id=thread_id or str(uuid.uuid4()),
            initial_values=initial_values,
        )

        try:
            state.start_execution()
            state.total_steps = len(self.workflow["nodes"])

            # Execute from the specified node
            try:
                await self._execute_from_node_recursive(
                    start_node_id, state, set()
                )

                state.complete_execution()
            except ValueError as e:
                state.fail_execution(str(e))

        except Exception as e:
            state.fail_execution(str(e))
            raise

        try:
            if initial_values.get("message") and persist:
                asyncio.create_task(
                    state.get_memory().add_input_output(
                        initial_values.get("message", ""),
                        state.output
                    )
                )
        except Exception as e:
            logger.error(f"Error adding message to memory: {e}")
        return state

    def _find_starting_nodes(self) -> List[str]:
        """Find nodes with no incoming edges (starting nodes)."""
        target_edges = self.workflow["target_edges"]

        input_node = None
        for node in self.workflow["nodes"]:
            if "input" in node["type"].lower():
                input_node = node
                break

        if input_node:
            return [input_node["id"]]

        starting_nodes = []
        for node in self.workflow["nodes"]:
            node_id = node["id"]
            if node_id not in target_edges or not target_edges[node_id]:
                starting_nodes.append(node_id)

        return starting_nodes

    async def _execute_from_node_recursive(
        self, node_id: str, state: WorkflowState, visited: Set[str]
    ) -> None:
        """Recursively execute nodes starting from a specific node."""
        if node_id in visited:
            return  # Avoid cycles

        visited.add(node_id)

        node_output: Optional[dict] = None

        # Check if aggregator requirements are satisfied
        node = self.executable_node(node_id, state)
        executable_node = node.check_if_requirement_satisfied()
        if executable_node:
            # All sources are ready, execute the aggregator
            node_output = await self._execute_single_node(node_id, state)
        else:
            # Requirements not satisfied, skip execution and continue flow
            logger.debug(
                f"Aggregator {node_id} requirements not satisfied, skipping execution"
            )
            return

        # Handle next nodes based on execution result
        if node_output and "next_nodes" in node_output:
            next_nodes = node_output.get("next_nodes", [])
        else:
            next_nodes = self._find_next_nodes(node_id)

        # Find and execute next nodes in parallel
        if next_nodes:
            # Capture tenant context from the main request scope
            tenant_id = get_tenant_context()

            async def execute_node_isolated(
                next_node_id: str,
                visited_set: Set[str],
                tenant: str,
                run_in_new_scope: bool,
            ):
                """
                Execute a node, optionally inside a fresh request scope.

                Important:
                - When executing multiple next-nodes in parallel, we MUST isolate request-scoped
                  dependencies (especially AsyncSession). Sharing a single AsyncSession across
                  concurrent tasks will raise:
                  "This session is provisioning a new connection; concurrent operations are not permitted".
                """
                if not run_in_new_scope:
                    return await self._execute_from_node_recursive(
                        next_node_id, state, visited_set
                    )

                request_scope_factory = injector.get(RequestScopeFactory)
                async with request_scope_factory.create_scope():
                    # Preserve tenant context in the new scope
                    set_tenant_context(tenant)
                    try:
                        return await self._execute_from_node_recursive(
                            next_node_id, state, visited_set
                        )
                    finally:
                        # Ensure any DI-created session is closed for this scope.
                        # (AsyncSession usually doesn't open a connection until first use, so this
                        # is cheap even for "no DB" nodes.)
                        try:
                            session = injector.get(AsyncSession)
                            await session.close()
                        except Exception:  # pylint: disable=broad-except
                            pass

            # Create tasks for all next nodes
            next_tasks = []
            for next_node_id in next_nodes:
                # Create a copy of visited set for each task to avoid conflicts
                task_visited = visited.copy()

                task = asyncio.create_task(
                    execute_node_isolated(
                        next_node_id=next_node_id,
                        visited_set=task_visited,
                        tenant=tenant_id,
                        # Only isolate when we are actually running parallel branches.
                        run_in_new_scope=(len(next_nodes) > 1),
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

    def _find_next_nodes(self, node_id: str) -> List[str]:
        """Find next nodes connected to the current node."""
        source_edges = self.workflow["source_edges"]

        next_nodes = []
        for edge in source_edges.get(node_id, []):
            next_nodes.append(edge["target"])

        return next_nodes

   

    def get_node_config(self, node_id: str):
        """Get the node config and type."""
        node_config = next(
            node for node in self.workflow["nodes"] if node["id"] == node_id)
        node_type = node_config.get("type", "")
        return node_config, node_type

    def executable_node(
        self, node_id: str, state: WorkflowState
    ) -> BaseNode:
        """Create an executable node instance."""
        node_config, node_type = self.get_node_config(node_id)
        node_class = self.__class__._node_registry.get(node_type)
        if not node_class:
            raise ValueError(
                f"Unknown node type: {node_type}, skipping node {node_id}")
        node = node_class(node_id, node_config, state)
        return node

    async def _execute_single_node(
        self, node_id: str, state: WorkflowState
    ) -> Any:
        """
        Execute a single node.
        
        Note: Request scope creation is handled at the parallel execution level
        to optimize connection pool usage. This method executes within the
        existing scope (either from the main request or from parallel execution).
        """
        try:
            node = self.executable_node(node_id, state)
            # Execute the node
            output = await node.execute()

            state.current_step += 1
            return output

        except Exception as e:
            logger.error(f"Error executing node {node_id}: {e}")
            state.fail_execution(f"Node {node_id} failed: {str(e)}")
            raise

    def get_workflow_status(self) -> Dict[str, Any]:
        """Get the current status of the workflow."""
        return {
            "workflow_id": self.workflow_id,
            "metadata": self.workflow["metadata"],
            "node_count": len(self.workflow["nodes"]),
            "edge_count": len(self.workflow["edges"]),
            "registered": True,
        }
