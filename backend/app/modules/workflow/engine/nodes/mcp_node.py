import logging
from typing import Dict, Any, List, Literal
import json

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.mcp.mcp_client import MCPClientV2

logger = logging.getLogger(__name__)


def convert_json_schema_to_parameters(
    input_schema: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Convert JSON Schema format to the parameter format expected by BaseTool.

    JSON Schema format:
    {
        "type": "object",
        "properties": {
            "param_name": {
                "type": "string",
                "description": "..."
            }
        },
        "required": ["param_name"]
    }

    Expected format:
    {
        "param_name": {
            "type": "string",
            "description": "...",
            "required": True
        }
    }
    """
    if not input_schema or not isinstance(input_schema, dict):
        return {}

    properties = input_schema.get("properties", {})
    required_fields = input_schema.get("required", [])

    if not isinstance(required_fields, list):
        required_fields = []

    parameters = {}
    for param_name, param_schema in properties.items():
        if isinstance(param_schema, dict):
            param_info = {
                "type": param_schema.get("type", "string"),
                "description": param_schema.get("description", ""),
                "required": param_name in required_fields,
            }
            # Add default value if present
            if "default" in param_schema:
                param_info["default"] = param_schema["default"]
            parameters[param_name] = param_info
        else:
            # If param_schema is not a dict, create a basic entry
            parameters[param_name] = {
                "type": "string",
                "description": "",
                "required": param_name in required_fields,
            }

    return parameters


class MCPNode(BaseNode):
    """MCP node that connects to external MCP servers and exposes tools to agents"""

    def _get_mcp_client(self, node_data: Dict[str, Any]) -> MCPClientV2:
        """
        Get MCP client based on node configuration.

        Args:
            node_data: Node configuration data

        Returns:
            MCPClientV2 instance

        Raises:
            ValueError: If connectionType or connectionConfig is missing
        """
        connection_type_raw = node_data.get("connectionType")
        connection_config = node_data.get("connectionConfig", {})

        if not connection_type_raw or connection_type_raw not in ("stdio", "sse", "http"):
            raise ValueError(
                "MCP node: connectionType is required. Must be one of: 'stdio', 'sse', 'http'"
            )

        connection_type: Literal["stdio", "sse", "http"] = connection_type_raw  # type: ignore[assignment]

        if not connection_config:
            raise ValueError("MCP node: connectionConfig is required")

        return MCPClientV2(connection_type, connection_config)

    def get_tools(self) -> List[BaseTool]:
        """
        Get list of BaseTool objects for whitelisted MCP tools.
        This method is called by BaseNode.get_connected_nodes to expose multiple tools.

        Returns:
            List of BaseTool objects, one for each whitelisted tool
        """
        node_data = self.get_node_data()
        available_tools = node_data.get("availableTools", [])
        whitelisted_tools = node_data.get("whitelistedTools", [])

        # Validate configuration
        connection_type = node_data.get("connectionType")
        connection_config = node_data.get("connectionConfig", {})

        if not connection_type:
            logger.warning(
                f"MCP node {self.node_id} has no connectionType configured"
            )
            return []

        if not connection_config:
            logger.warning(
                f"MCP node {self.node_id} has no connectionConfig configured"
            )
            return []

        if not whitelisted_tools:
            logger.debug(f"MCP node {self.node_id} has no whitelisted tools")
            return []

        tools = []
        for tool_name in whitelisted_tools:
            # Find the tool definition in available_tools
            tool_def = next(
                (t for t in available_tools if t.get("name") == tool_name), None
            )

            if not tool_def:
                logger.warning(
                    f"Whitelisted tool '{tool_name}' not found in available tools for MCP node {self.node_id}"
                )
                continue

            # Create a BaseTool for this MCP tool
            tool_description = tool_def.get("description", f"MCP tool: {tool_name}")
            tool_input_schema = tool_def.get("inputSchema", {})

            # Convert JSON Schema format to parameter format expected by BaseTool
            tool_parameters = convert_json_schema_to_parameters(tool_input_schema)

            # Create a closure to capture tool_name and node_data
            # The function passed to BaseTool should be async-compatible
            # BaseTool.invoke calls function({"parameters": kwargs}) and if it's async,
            # the agent will await the coroutine
            def create_tool_executor(captured_tool_name: str):
                """Create an async function that executes a specific MCP tool"""

                async def tool_executor(input_data: Dict[str, Any]) -> str:
                    """Execute the MCP tool asynchronously"""
                    try:
                        # Extract parameters from input_data
                        parameters = input_data.get("parameters", {})

                        # Validate tool is still whitelisted (security check)
                        current_node_data = self.get_node_data()
                        current_whitelist = current_node_data.get("whitelistedTools", [])
                        if captured_tool_name not in current_whitelist:
                            error_msg = (
                                f"Tool '{captured_tool_name}' is not whitelisted"
                            )
                            logger.error(error_msg)
                            return json.dumps({"error": error_msg})

                        # Get MCP client
                        mcp_client = self._get_mcp_client(current_node_data)
                        result = await mcp_client.execute_tool(
                            captured_tool_name, parameters
                        )

                        # Convert result to string (BaseTool.invoke returns str)
                        if isinstance(result, (dict, list)):
                            return json.dumps(result)
                        else:
                            return str(result)
                    except Exception as e:
                        error_msg = (
                            f"Error executing MCP tool '{captured_tool_name}': {str(e)}"
                        )
                        logger.error(error_msg, exc_info=True)
                        return json.dumps({"error": error_msg})

                return tool_executor

            # Create the executor function (returns async function)
            executor_func = create_tool_executor(tool_name)

            tool = BaseTool(
                node_id=f"{self.node_id}:{tool_name}",  # Unique ID combining node and tool
                name=tool_name,
                description=tool_description,
                parameters=tool_parameters,
                function=executor_func,
                return_direct=node_data.get("returnDirect", False),
            )

            tools.append(tool)
            logger.debug(f"Created tool '{tool_name}' for MCP node {self.node_id}")

        return tools

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an MCP node execution.

        This method is called when the node is executed directly (e.g., via test-node endpoint).
        For normal workflow execution, tools are exposed via get_tools() and executed individually.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with tool execution results
        """
        node_data = config
        tool_name = config.get("tool_name")  # From input_data when testing
        tool_arguments = config.get("tool_arguments", {})

        # Validate required parameters
        connection_type = node_data.get("connectionType")
        connection_config = node_data.get("connectionConfig", {})

        if not connection_type:
            error_msg = "MCP node: connectionType is required. Must be one of: 'stdio', 'sse', 'http'"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        if not connection_config:
            error_msg = "MCP node: connectionConfig is required"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        if not tool_name:
            error_msg = "MCP node: tool_name is required for direct execution"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        # Validate tool is whitelisted
        whitelisted_tools = node_data.get("whitelistedTools", [])
        if tool_name not in whitelisted_tools:
            error_msg = f"Tool '{tool_name}' is not whitelisted. Whitelisted tools: {whitelisted_tools}"
            logger.error(error_msg)
            return {"status": 403, "data": {"error": error_msg}}

        try:
            # Get MCP client
            mcp_client = self._get_mcp_client(node_data)
            result = await mcp_client.execute_tool(tool_name, tool_arguments)

            return {"status": "success", "output": result}

        except ValueError as e:
            # Validation or MCP server error
            error_msg = str(e)
            logger.error(f"MCP tool execution error: {error_msg}")
            return {"status": "error", "output": error_msg}
        except Exception as e:
            error_msg = f"Error executing MCP tool '{tool_name}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "output": error_msg}
