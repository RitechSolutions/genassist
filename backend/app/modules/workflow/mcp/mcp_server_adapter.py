"""
MCP Server Adapter using the official MCP Python SDK.

This adapter bridges FastAPI routes with the MCP SDK to properly expose workflows as MCP tools.
"""

import logging
from typing import Dict, Any, List
import json
import uuid

from mcp.types import Tool, TextContent
from mcp.server import Server

from app.modules.workflow.engine.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


class WorkflowMCPServerAdapter:
    """
    Adapter that converts workflows to MCP tools and handles tool execution.
    Uses MCP SDK types for proper protocol compliance.
    """

    def __init__(
        self,
        mcp_server,
        workflow_repo,
    ):
        """
        Initialize the adapter.

        Args:
            mcp_server: MCPServerResponse instance
            workflow_repo: WorkflowRepository instance
        """
        self.mcp_server = mcp_server
        self.workflow_repo = workflow_repo

    async def list_tools(self) -> List[Tool]:
        """
        List available tools from workflows as MCP Tool objects.

        Returns:
            List of MCP Tool objects
        """
        tools = []

        for workflow_mapping in self.mcp_server.workflows:
            # Get workflow to extract input schema
            workflow_model = await self.workflow_repo.get_by_id(
                workflow_mapping.workflow_id
            )

            if not workflow_model:
                logger.warning(
                    f"Workflow {workflow_mapping.workflow_id} not found for tool {workflow_mapping.tool_name}"
                )
                continue

            # Extract input schema from chatInputNode
            from app.services.mcp_server import (
                _extract_input_schema_from_chat_input_node,
            )

            input_schema = _extract_input_schema_from_chat_input_node(workflow_model)

            # Create MCP Tool object
            tool = Tool(
                name=workflow_mapping.tool_name,
                description=workflow_mapping.tool_description or "",
                inputSchema=input_schema,
            )
            tools.append(tool)

        return tools

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> List[TextContent]:
        """
        Execute a workflow as an MCP tool.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            CallToolResult with tool execution output

        Raises:
            ValueError: If tool is not found
        """
        # Find workflow by tool name
        workflow_mapping = None
        for wf in self.mcp_server.workflows:
            if wf.tool_name == tool_name:
                workflow_mapping = wf
                break

        if not workflow_mapping:
            raise ValueError(
                f"Tool '{tool_name}' not found or not exposed by this server"
            )

        # Get workflow
        workflow_model = await self.workflow_repo.get_by_id(
            workflow_mapping.workflow_id
        )
        if not workflow_model:
            raise ValueError("Workflow not found")

        try:
            # Prepare workflow execution input
            workflow_config = {
                "id": str(workflow_mapping.workflow_id),
                "nodes": workflow_model.nodes or [],
                "edges": workflow_model.edges or [],
            }

            # Create workflow engine with the configuration
            workflow_engine = WorkflowEngine(workflow_config)

            # Execute workflow
            thread_id = f"mcp_tool_{uuid.uuid4()}"
            state = await workflow_engine.execute_from_node(
                input_data=arguments,
                thread_id=thread_id,
            )

            # Format response
            result = state.format_state_as_response()

            output = result.get("output", {})
            if isinstance(output, dict):
                output = json.dumps(output, indent=2, ensure_ascii=False)
            elif isinstance(output, str):
                output = output
            else:
                output = str(output)

            text_content = TextContent(type="text", text=output)

            # Return list of ContentBlock - the SDK will wrap it in CallToolResult
            return [text_content]

        except Exception as e:
            logger.error(f"Error executing MCP tool '{tool_name}': {e}", exc_info=True)
            raise ValueError(f"Workflow execution failed: {str(e)}")


def create_mcp_server_instance(mcp_server, workflow_repo) -> Server:
    """
    Create an MCP Server instance configured with workflows as tools.

    Args:
        mcp_server: MCPServerResponse instance
        workflow_repo: WorkflowRepository instance

    Returns:
        Configured MCP Server instance
    """
    adapter = WorkflowMCPServerAdapter(mcp_server, workflow_repo)

    # Create server instance
    server = Server("workflow-mcp-server")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        """List available tools."""
        return await adapter.list_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]):
        """Execute a tool."""
        # Return List[TextContent] - the SDK decorator will wrap it in CallToolResult
        # The decorator expects UnstructuredContent (Iterable[ContentBlock]), which List[TextContent] satisfies
        return await adapter.call_tool(name, arguments)

    return server
