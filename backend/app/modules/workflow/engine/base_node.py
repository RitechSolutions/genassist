"""
Base node class for workflow execution with state management.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Literal, Optional, List
import logging
import time
from app.modules.workflow.engine.utils import replace_config_vars
from app.modules.workflow.engine.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


class BaseNode(ABC):
    """
    Base class for all workflow nodes.

    This class provides:
    - State management access
    - Configuration handling
    - Execution tracking
    - Input/output processing
    """

    def __init__(self,
                 node_id: str,
                 node_config: Dict[str, Any],
                 state: WorkflowState):
        """
        Initialize the base node.

        Args:
            node_id: Unique identifier for the node
            node_config: Configuration data for the node
            state: Workflow state instance
        """
        self.node_id = node_id
        self.node_config = node_config or {}
        self.node_data: dict[str, Any] = node_config.get("data", {})
        self.state = state
        self.input_data = None
        self.output_data = None
        self.execution_start_time: Optional[float] = None
        self.execution_end_time: Optional[float] = None

        # Validate configuration
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate node configuration. Override in subclasses for custom validation."""
        if not self.node_id:
            raise ValueError("Node ID is required")
        if not self.node_config:
            logger.warning(f"Node {self.node_id} has no configuration")

    def get_name(self) -> str:
        """Get the node name from configuration."""
        return self.node_data.get("name", f"Node_{self.node_id}")

    def get_last_node_output(self) -> Any:
        """Get the output of the last node."""
        return self.state.get_last_node_output()

    def get_node_data(self) -> dict:
        """Get the node data from configuration."""
        return self.node_data

    def get_type(self) -> str:
        """Get the node type from configuration."""
        return self.node_config.get("type", "unknown")

    def get_node_config(self, node_id: str):
        """Get the node config and type."""
        workflow = self.state.workflow
        node_config = next(
            node for node in workflow["nodes"] if node["id"] == node_id)
        node_type = node_config.get("type", "")
        return node_config, node_type

    def get_handlers(self) -> list:
        """Get the node handlers from configuration."""
        return self.node_data.get("handlers", [])

    def get_description(self) -> str:
        """Get the node description from configuration."""
        return self.node_data.get("description", "")

    def get_input_schema(self) -> dict:
        """Get the node input schema from configuration."""
        return self.node_data.get("inputSchema", {})

    def get_state(self) -> WorkflowState:
        """Get the workflow state."""
        return self.state

    def set_node_output(self, output: Any) -> None:
        """Set the node output and save to state."""
        self.output_data = output
        self.state.set_node_output(self.node_id, output)
        logger.debug(f"Node {self.node_id} output set: {output}")

    def set_node_input(self, input_data: Any) -> None:
        """Set the node input and save to state."""
        self.input_data = input_data
        self.state.set_node_input(self.node_id, input_data)
        logger.debug(f"Node {self.node_id} input set: {input_data}")

    def get_input(self) -> Any:
        """Get the current input data."""
        return self.input_data

    def get_output(self) -> Any:
        """Get the current output data."""
        return self.output_data

    def get_memory(self):
        """Get the conversation memory."""
        return self.state.get_memory()

    def get_session_context(self) -> dict:
        """Get the session context (session data) from workflow state."""
        return self.state.get_session()

    def get_source_nodes(self) -> List[str]:
        """Get all source nodes connected to this next node."""
        target_edges = self.state.target_edges
        incoming_edges = target_edges.get(self.node_id, [])
        source_nodes = []
        for edge in incoming_edges:
            source_id = edge.get("source")
            if source_id:
                _, node_type = self.get_node_config(source_id)
                if "toolBuilderNode" or "mcpNode" in node_type:
                    # skip tool builder node because it does not produce output normally
                    continue
                source_nodes.append(source_id)

        logger.debug(
            f"Found {len(source_nodes)} source nodes for next node {self.node_id}: {source_nodes}")
        return source_nodes

    def check_if_requirement_satisfied(self) -> bool:
        """
        Check if all requirements for this node are satisfied.

        This method can be overridden by subclasses to implement
        custom requirement checking logic.

        Returns:
            True if all requirements are satisfied, False otherwise
        """
        source_nodes = self.get_source_nodes()

        # Check if all source nodes have outputs
        for source_id in source_nodes:
            source_output = self.state.get_node_output(source_id)
            if source_output is None:
                logger.debug(
                    f"Source node {source_id} not ready for next node {self.node_id}")
                return False

        logger.debug(
            f"All requirements satisfied for node: {self.node_id}")
        return True

    def start_execution(self) -> None:
        """Start node execution tracking."""
        self.execution_start_time = time.time()
        self.state.start_node_execution(self.node_id)
        logger.debug(f"Node {self.node_id} execution started")

    def complete_execution(self, error: Optional[str] = None) -> None:
        """Complete node execution tracking."""
        self.execution_end_time = time.time()
        if error:
            self.state.complete_node_execution(
                self.node_id, self.output_data, error)
        else:
            self.state.complete_node_execution(
                self.node_id, self.output_data, None)
        logger.debug(f"Node {self.node_id} execution completed")

    def get_execution_time(self) -> float:
        """Get the execution time in seconds."""
        if self.execution_start_time and self.execution_end_time:
            return self.execution_end_time - self.execution_start_time
        return 0.0

    async def dummy_process(self, config: Optional[Dict[str, Any]] = None, node_input: Any = None) -> Any:
        if config is None:
            config = {}
        logger.info(f"Dummy process called for node {self.node_id}")
        logger.info(f"Node input: {node_input}")
        logger.info(f"Node config: {config}")
        return f"Success on node_input: {node_input}"

    def get_connected_nodes(self, tag: Literal["tools", "starter", "true", "false", "default"]) -> list:
        """
        Get connected source nodes, optionally filtered by target handle, in BaseTool format.

        This method finds all nodes connected to this node through incoming edges
        and converts them to BaseTool format similar to the old workflow system.

        Args:
            target_handle: Optional target handle to filter edges (e.g., "input_tools")

        Returns:
            List of BaseTool objects for connected source nodes
        """

        connected_nodes = []

        # Get target edges information from the workflow state
        target_edges = self.state.target_edges
        source_edges = self.state.source_edges

        # Get all incoming edges for this node
        incoming_edges = target_edges.get(self.node_id, [])
        outgoing_edges = source_edges.get(self.node_id, [])

        all_edges = incoming_edges + outgoing_edges

        if not all_edges:
            logger.debug("No edges found for node %s", self.node_id)
            return []

        # Process each incoming edge
        for edge in incoming_edges:
            edge_target_handle = edge.get("targetHandle", "")

            if tag not in edge_target_handle:
                continue

            # Check if this is a "tools" type connection (for tools)
            if "tools" in edge_target_handle:

                from app.modules.workflow.agents.base_tool import BaseTool
                from app.modules.workflow.engine.workflow_engine import WorkflowEngine

                source_node_id = edge.get("source")

                workflow_engine = WorkflowEngine.get_instance()

                workflow_id = self.get_state().workflow_id
                if not workflow_id or not isinstance(workflow_id, str):
                    logger.warning(
                        "No workflow id found for node %s", self.node_id)
                    continue
                node = workflow_engine.executable_node(
                    source_node_id, self.get_state(), workflow_id)

                if node:
                    # Check if node exposes multiple tools (e.g., MCP node)
                    if hasattr(node, 'get_tools') and callable(getattr(node, 'get_tools')):
                        # Node exposes multiple tools
                        tools = node.get_tools()
                        connected_nodes.extend(tools)
                        logger.debug("Added %d tools from node %s",
                                     len(tools), source_node_id)
                    else:
                        # Standard single tool node
                        tool = BaseTool(
                            node_id=source_node_id,
                            name=node.get_name(),
                            description=node.get_description(),
                            parameters=node.get_input_schema(),
                            return_direct=node.get_node_data().get("returnDirect", False),
                            function=node.execute
                        )

                        connected_nodes.append(tool)
                        logger.debug("Added tool: %s from node %s",
                                     tool.name, source_node_id)

            else:
                source_node_id = edge.get("target")
                connected_nodes.append(source_node_id)
        for edge in outgoing_edges:
            edge_source_handle = edge.get("sourceHandle", "")
            if tag not in edge_source_handle:
                continue
            source_node_id = edge.get("target")
            connected_nodes.append(source_node_id)

        return connected_nodes

    async def execute(self, direct_input: Any = None) -> Any:  # pylint: disable=unused-argument
        """
        Execute the node with the given input data.

        This method:
        1. Sets up execution tracking
        2. Processes input data
        3. Calls the abstract process method with resolved config
        4. Tracks execution completion
        5. Returns the output

        Args:
            input_data: Input data for the node

        Returns:
            The processed output from the node
        """
        try:

            # Start execution tracking
            self.start_execution()
            # self.set_node_input(input_data)

            # Resolve configuration template variables
            source_output = self.get_input_from_source()
            resolved_config, replacements = replace_config_vars(
                config=self.node_config, state=self.state, source_output=source_output, direct_input=direct_input)

            node_config = resolved_config.get(
                "data", None) or resolved_config or {}

            # Log replacements for debugging
            if replacements:
                logger.debug("Node %s variable replacements: %s",
                             self.node_id, replacements)

            self.set_node_input(replacements)
            # Process the node (implemented by subclasses)
            result = await self.process(node_config)

            # Set output data
            if result is not None:
                self.set_node_output(result)

            # Complete execution tracking
            self.complete_execution()

            return result

        except Exception as e:
            error_msg = f"Error executing node {self.node_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.complete_execution(error=error_msg)
            raise

    @abstractmethod
    async def process(self, config: Dict[str, Any]) -> Any:
        """
        Process the node with the resolved configuration.

        This is the main method that subclasses must implement.
        The config parameter contains the node configuration with all
        template variables resolved to their actual values.

        Args:
            config: The resolved configuration for the node

        Returns:
            The processed output from the node
        """
        raise NotImplementedError(
            "Subclasses must implement the process method")

    def get_input_from_source(self) -> Any:
        """
        Get the output from the last connected source node.

        This method finds the most recently connected source node and returns its output.
        If multiple source nodes are connected, it returns the output from the last one
        (which would typically be the most recent in the execution order).

        Returns:
            The output from the last connected source node, or None if no sources
        """
        all_target_edges = self.get_state().target_edges
        target_edges = all_target_edges.get(self.node_id, [])
        input_edges = [edge for edge in target_edges if edge.get(
            "targetHandle", "") == "input"]
        if not input_edges:
            logger.debug("No target edges found for node %s", self.node_id)
            return None

        # Get the last edge (most recent source)
        if len(input_edges) == 1:
            last_edge = input_edges[-1]
            source_node_id = last_edge["source"]
            # Get the output from the source node
            source_output = self.get_state().get_node_output(source_node_id)

            logger.debug("Node %s retrieved output from source node %s: %s",
                         self.node_id, source_node_id, source_output)
        else:
            source_output = {}
            for edge in input_edges:
                source_node_id = edge["source"]
                source_output = {
                    **source_output, **{source_node_id: self.get_state().get_node_output(source_node_id)}}

        return source_output

    def __str__(self) -> str:
        """String representation of the node."""
        return f"{self.__class__.__name__}(id={self.node_id}, name={self.get_name()})"

    def __repr__(self) -> str:
        """Detailed string representation of the node."""
        return f"{self.__class__.__name__}(id={self.node_id}, name={self.get_name()}, type={self.get_type()})"
