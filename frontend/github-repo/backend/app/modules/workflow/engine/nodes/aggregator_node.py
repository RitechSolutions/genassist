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

        logger.info(
            f"Sync aggregator node {self.node_id} starting with strategy: {aggregation_strategy}")

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
        aggregated_outputs = self._aggregate_immediately(source_nodes)
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

        logger.info(
            f"Sync aggregator node {self.node_id} completed with {len(aggregated_outputs)} outputs")
        return result



    def _aggregate_immediately(self, source_nodes: List[str]) -> Dict[str, Any]:
        """
        Immediately aggregate outputs from all source nodes.
        No waiting - assumes all sources are ready.

        Args:
            source_nodes: List of source node IDs to aggregate

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
                logger.warning(f"Source node {source_id} not ready - skipping")

        if missing_sources:
            logger.warning(f"Some source nodes not ready: {missing_sources}")

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
