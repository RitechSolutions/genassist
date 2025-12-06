from typing import Dict, Any, List, Optional
import logging
from app.modules.agents.workflow.base_processor import NodeProcessor

logger = logging.getLogger(__name__)

class ToolBuilderNodeProcessor(NodeProcessor):
    """Processor for Tool Builder nodes that execute subflows and return tool references"""
    
    async def _find_subflow_nodes(self) -> tuple[List[str], List[str]]:
        """Find the start and end nodes of the subflow"""
        start_nodes = []
        end_nodes = []
        
        # Find nodes connected to starter_processor
        for edge in self.get_context().get_source_edges(self.node_id):
            if edge.get("sourceHandle") == "starter_processor":
                start_nodes.append(edge.get("target"))
        
        # Find nodes connected to end_processor
        for edge in self.get_context().get_target_edges(self.node_id):
            if edge.get("targetHandle") == "end_processor":
                end_nodes.append(edge.get("source"))
        
        logger.info(f"ToolBuilder subflow - Start nodes: {start_nodes}, End nodes: {end_nodes}")
        return start_nodes, end_nodes
    
    async def _execute_subflow(self, start_nodes: List[str], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the subflow starting from the given nodes"""
        results = {}
        visited = set()
        end_nodes_fallback = set()

        for start_node_id in start_nodes:
            try:
                # Get the node processor for the start node
                start_processor = self.get_context().get_node_processor(start_node_id)
                if not start_processor:
                    logger.error(f"No processor found for start node {start_node_id}")
                    results[start_node_id] = {"error": "No processor found"}
                    continue

                # Execute the start node and its successors, collecting fallback end nodes
                await self._execute_node_and_successors(start_node_id, visited, end_nodes_fallback)

                # Collect results from end nodes
                _, end_nodes = await self._find_subflow_nodes()
                if not end_nodes:
                    end_nodes = list(end_nodes_fallback)

                logger.info(f"ToolBuilder subflow - End nodes: {end_nodes}")
                for end_node_id in end_nodes:
                    end_processor = self.get_context().get_node_processor(end_node_id)
                    if end_processor:
                        print(f"End node {end_node_id} results: {end_processor.get_output()}")
                        results[end_node_id] = end_processor.get_output()

            except Exception as e:
                logger.error(f"Error executing subflow for start node {start_node_id}: {e}")
                results[start_node_id] = {"error": str(e)}

        return results

    async def _execute_node_and_successors(self, node_id: str, visited: set, end_nodes: set):
        """Execute a node and all its successors in the subflow, marking as end node if no next nodes"""
        if node_id in visited or node_id == self.node_id:
            return

        visited.add(node_id)

        # Get the node processor
        processor = self.get_context().get_node_processor(node_id)
        if not processor:
            logger.error(f"No processor found for node {node_id}")
            return

        # Execute the node
        await processor.process(self.get_input())

        # Get next nodes in the subflow
        next_nodes = self._get_next_nodes_in_subflow(node_id)
        if not next_nodes:
            end_nodes.add(node_id)
        for next_node_id in next_nodes:
            await self._execute_node_and_successors(next_node_id, visited, end_nodes)
    
    def _get_next_nodes_in_subflow(self, node_id: str) -> List[str]:
        """Get the next nodes in the subflow, excluding the tool builder node"""
        next_nodes = []
        for edge in self.get_context().get_source_edges(node_id):
            target = edge.get("target")
            if target and target != self.node_id:
                next_nodes.append(target)
        return next_nodes
    
    async def process(self, input_data: Any = None) -> Dict[str, Any]:
        """Process the tool builder node by executing its subflow"""
        try:
            # Get input data
            input_data = await self.get_process_input(input_data)
            self.set_input(input_data)
            
            # Find subflow start and end nodes
            start_nodes, end_nodes = await self._find_subflow_nodes()
            
            if not start_nodes:
                logger.warning("No start nodes found for ToolBuilder subflow")
                self.save_output({"error": "No start nodes found for subflow"})
                return self.get_output()
            
            # Execute the subflow
            subflow_results = await self._execute_subflow(start_nodes, input_data)
            
            # Return only the first value from subflow_results
            output = None
            if subflow_results:
                output = next(iter(subflow_results.values()))
            else:
                output = {"error": "No subflow results"}
            
            self.save_output(output)
            logger.info(f"ToolBuilder completed with {len(subflow_results)} subflow results")
            return self.get_output()
            
        except Exception as e:
            error_msg = f"Error processing ToolBuilder node: {str(e)}"
            logger.error(error_msg)
            self.save_output({"error": error_msg})
            return self.get_output() 