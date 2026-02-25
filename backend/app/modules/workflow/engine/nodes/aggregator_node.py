"""
Aggregator node implementation that waits for multiple source nodes to complete.
"""

from typing import Dict, Any, List
import logging

from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class AggregatorNode(BaseNode):
    """
    Aggregator node that waits for multiple source nodes to provide outputs
    before proceeding with execution.

    This node is useful for scenarios where you need to combine outputs
    from multiple parallel branches before continuing the workflow.
    """

    def check_if_requirement_satisfied(self) -> bool:
        """
        Check if the aggregator is ready to execute.

        When requireAllInputs is True (default), all source nodes must have
        outputs before proceeding. When False, at least one finished source
        is enough.
        """
        require_all_inputs = self.node_data.get("requireAllInputs", True)

        if require_all_inputs:
            return super().check_if_requirement_satisfied()

        # Partial mode: proceed if at least one source has output
        source_nodes = self.get_source_nodes()
        if not source_nodes:
            return True

        for source_id in source_nodes:
            if self.state.get_node_output(source_id) is not None:
                logger.debug(
                    f"Aggregator {self.node_id} has at least one ready source ({source_id}), proceeding (requireAllInputs=false)")
                return True

        logger.debug(
            f"Aggregator {self.node_id} has no ready sources yet")
        return False

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an aggregator node by immediately checking for source outputs.
        No waiting - assumes sources are already complete.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary containing aggregated outputs from all source nodes
        """
        # Get configuration values
        aggregation_strategy = config.get("aggregationStrategy", "merge")
        required_sources = config.get("requiredSources", [])
        require_all_inputs = config.get("requireAllInputs", True)

        logger.info(
            f"Sync aggregator node {self.node_id} starting with strategy: {aggregation_strategy}, requireAllInputs: {require_all_inputs}")

        # Get all source nodes connected to this aggregator
        source_nodes = self.get_source_nodes()
        if not source_nodes:
            try:
                source_nodes = list(self.get_state().node_outputs.keys())
            except Exception:
                source_nodes = []
        if not source_nodes:
            logger.warning(
                f"No source nodes found for aggregator {self.node_id}")
            return {"error": "No source nodes found", "aggregated_outputs": {}}

        # If specific sources are required, validate they exist
        if required_sources:
            missing_sources = set(required_sources) - set(source_nodes)
            if missing_sources:
                logger.error(
                    f"Required source nodes not found: {missing_sources}")
                return {"error": f"Required source nodes not found: {missing_sources}", "aggregated_outputs": {}}

        # Immediately aggregate available outputs
        aggregated_outputs = self._aggregate_immediately(source_nodes, require_all_inputs)
        aggregated_outputs = self._apply_aggregation_strategy(aggregated_outputs, aggregation_strategy)
        # Set input for tracking
        self.set_node_input({
            "source_nodes": source_nodes,
            "aggregation_strategy": aggregation_strategy
        })

        result = {
            "aggregated_outputs": aggregated_outputs,
            "source_nodes": source_nodes,
            "aggregation_strategy": aggregation_strategy,
            "count": len(aggregated_outputs)
        }

        logger.debug(
            f"Sync aggregator node {self.node_id} completed with {len(aggregated_outputs)} outputs")
        return result



    def _aggregate_immediately(self, source_nodes: List[str], require_all_inputs: bool = True) -> Dict[str, Any]:
        """
        Immediately aggregate outputs from all source nodes.

        Args:
            source_nodes: List of source node IDs to aggregate
            require_all_inputs: If True, all sources must be ready (default).
                If False, only include sources that have finished.

        Returns:
            Dictionary containing aggregated outputs
        """
        aggregated_outputs = {}
        missing_sources = []

        for source_id in source_nodes:
            source_output = self.state.get_node_output(source_id)
            if source_output is not None:
                aggregated_outputs[source_id] = source_output
                logger.debug(
                    f"Source node {source_id} output: {source_output}")
            else:
                missing_sources.append(source_id)
                if require_all_inputs:
                    logger.warning(f"Source node {source_id} not ready - skipping")
                else:
                    logger.info(f"Source node {source_id} not finished - excluded (requireAllInputs=false)")

        if missing_sources:
            if require_all_inputs:
                logger.warning(f"Some source nodes not ready: {missing_sources}")
            else:
                logger.info(f"Proceeding without unfinished sources: {missing_sources}")

        return aggregated_outputs

    def _apply_aggregation_strategy(
        self,
        aggregated_outputs: Dict[str, Any],
        aggregation_strategy: str
    ) -> Dict[str, Any]:
        """Apply the specified aggregation strategy to the outputs."""
        if aggregation_strategy == "merge":
            return self._merge_outputs(aggregated_outputs)
        elif aggregation_strategy == "list":
            return self._list_outputs(aggregated_outputs)
        elif aggregation_strategy == "concat":
            return self._concat_outputs(aggregated_outputs)
        else:
            logger.warning(
                f"Unknown aggregation strategy: {aggregation_strategy}, using merge")
            return self._merge_outputs(aggregated_outputs)

    def _merge_outputs(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Merge outputs from all source nodes into a single dictionary."""
        merged = {}
        for output in outputs.values():
            if isinstance(output, dict):
                merged.update(output)
            else:
                merged[output] = output
        return merged

    def _list_outputs(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Create a list of outputs from all source nodes."""
        return {
            "outputs": list(outputs.values()),
            "node_mapping": {node_id: i for i, node_id in enumerate(outputs.keys())}
        }

    def _concat_outputs(self, outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Concatenate string outputs from all source nodes."""
        concatenated = ""
        for output in outputs.values():
            if isinstance(output, str):
                concatenated += output
            else:
                concatenated += str(output)

        return {
            "concatenated_output": concatenated,
            "source_outputs": outputs
        }
