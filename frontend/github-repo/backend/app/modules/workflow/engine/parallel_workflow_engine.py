"""
Parallel workflow execution engine that handles aggregator nodes without blocking.
"""

import asyncio
import logging
from typing import Dict, Any, List, Set, Optional

from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


class ParallelWorkflowEngine(WorkflowEngine):
    """
    Enhanced workflow engine that supports true parallel execution
    without blocking on aggregator nodes.
    """

    async def execute_from_node_parallel(self,
                                         workflow_id: str,
                                         start_node_id: Optional[str] = None,
                                         input_data: Dict[str, Any] = {},
                                         thread_id: str = None) -> WorkflowState:
        """
        Execute workflow with true parallel execution support.

        This method:
        1. Identifies all nodes that can run in parallel
        2. Executes them concurrently using asyncio.gather
        3. Handles aggregator nodes by waiting for their dependencies
        4. Continues until all nodes are executed
        """
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if not start_node_id:
            start_node_ids = self._find_starting_nodes(workflow_id)
            if len(start_node_ids) == 1:
                start_node_id = start_node_ids[0]
            else:
                raise ValueError(
                    f"Multiple starting nodes found: {start_node_ids}")

        # Create execution state
        from app.modules.workflow.utils import process_path_based_input_data
        initial_values = process_path_based_input_data(input_data)

        state = WorkflowState(
            workflow=workflow,
            thread_id=thread_id or "parallel_execution",
            initial_values=initial_values
        )

        try:
            state.start_execution()
            state.total_steps = len(workflow["nodes"])

            # Execute workflow in parallel
            await self._execute_workflow_parallel(workflow_id, state, start_node_id)

            state.complete_execution()

        except Exception as e:
            state.fail_execution(str(e))
            raise

        return state

    async def _execute_workflow_parallel(self,
                                         workflow_id: str,
                                         state: WorkflowState,
                                         start_node_id: str) -> None:
        """Execute workflow with parallel node execution."""
        workflow = self.workflows[workflow_id]
        all_nodes = {node["id"]: node for node in workflow["nodes"]}
        executed_nodes = set()
        pending_tasks = {}

        # Start with the initial node
        initial_task = asyncio.create_task(
            self._execute_node_with_dependencies(
                start_node_id, state, workflow_id, executed_nodes)
        )
        pending_tasks[start_node_id] = initial_task

        # Continue until all nodes are executed
        while pending_tasks:
            # Wait for at least one task to complete
            done, pending = await asyncio.wait(
                pending_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED
            )

            # Process completed tasks
            for task in done:
                try:
                    result = await task
                    if result:
                        # Find next nodes that can now be executed
                        next_nodes = self._find_ready_nodes(
                            result, executed_nodes, workflow_id=workflow_id, state=state
                        )

                        # Start new tasks for ready nodes
                        for node_id in next_nodes:
                            if node_id not in pending_tasks and node_id not in executed_nodes:
                                new_task = asyncio.create_task(
                                    self._execute_node_with_dependencies(
                                        node_id, state, workflow_id, executed_nodes
                                    )
                                )
                                pending_tasks[node_id] = new_task

                except Exception as e:
                    logger.error(f"Task execution failed: {e}")

            # Remove completed tasks from pending
            pending_tasks = {k: v for k,
                             v in pending_tasks.items() if not v.done()}

    async def _execute_node_with_dependencies(self,
                                              node_id: str,
                                              state: WorkflowState,
                                              workflow_id: str,
                                              executed_nodes: Set[str]) -> Optional[str]:
        """Execute a single node, handling its dependencies."""
        if node_id in executed_nodes:
            return None

        workflow = self.workflows[workflow_id]
        node_config = next(
            node for node in workflow["nodes"] if node["id"] == node_id)
        node_type = node_config.get("type", "")

        # Check if this is an aggregator node
        if "aggregator" in node_type.lower():
            return await self._execute_aggregator_with_dependencies(
                node_id, state, workflow_id, executed_nodes
            )
        else:
            # Execute regular node
            await self._execute_single_node(node_id, state, workflow_id)
            executed_nodes.add(node_id)
            return node_id

    async def _execute_aggregator_with_dependencies(self,
                                                    node_id: str,
                                                    state: WorkflowState,
                                                    workflow_id: str,
                                                    executed_nodes: Set[str]) -> Optional[str]:
        """Execute aggregator node after ensuring all dependencies are ready."""
        workflow = self.workflows[workflow_id]
        target_edges = workflow["target_edges"]

        # Get source nodes
        source_nodes = []
        for edge in target_edges.get(node_id, []):
            source_id = edge["source"]
            source_nodes.append(source_id)

        # Wait for all source nodes to be executed
        while not all(source_id in executed_nodes for source_id in source_nodes):
            await asyncio.sleep(0.001)  # Very short wait

        # Now execute the aggregator
        await self._execute_single_node(node_id, state, workflow_id)
        executed_nodes.add(node_id)
        return node_id

    def _find_ready_nodes(self,
                          completed_node_id: str,
                          executed_nodes: Set[str],
                          workflow_id: str,
                          state: WorkflowState) -> List[str]:
        """Find nodes that are ready to execute after a node completes."""
        workflow = self.workflows[workflow_id]
        source_edges = workflow["source_edges"]
        ready_nodes = []

        # Check nodes that depend on the completed node
        for edge in source_edges.get(completed_node_id, []):
            target_id = edge["target"]

            if target_id in executed_nodes:
                continue

            node = self.executable_node(target_id, state, workflow_id)
            if node.check_if_requirement_satisfied():
                ready_nodes.append(target_id)

        return ready_nodes
