"""
MCP Client using the official MCP Python SDK.

Supports multiple connection types:
- STDIO: For local MCP servers running as processes
- HTTP/SSE: For remote MCP servers over HTTP/HTTPS
"""

import logging
from typing import Dict, Any, List, Optional, Literal
from contextlib import asynccontextmanager

from mcp import ClientSession as MCPClientSession
from mcp.client.stdio import stdio_client as mcp_stdio_client
from mcp.client.sse import sse_client as mcp_sse_client
from mcp.types import TextContent as MCPTextContent

logger = logging.getLogger(__name__)


class MCPConnectionManager:
    """
    Manages MCP client connections with support for different transport types.
    Handles connection lifecycle and session management.
    """

    def __init__(
        self,
        connection_type: Literal["stdio", "sse", "http"],
        connection_config: Dict[str, Any],
    ):
        """
        Initialize MCP connection manager.

        Args:
            connection_type: Type of connection ("stdio", "sse", or "http")
            connection_config: Configuration dictionary with connection-specific settings
        """
        self.connection_type = connection_type
        self.connection_config = connection_config
        self._session: Optional[Any] = None

    @asynccontextmanager
    async def get_session(self):
        """
        Get an MCP client session. Use as async context manager.

        Yields:
            ClientSession: MCP client session
        """
        if self.connection_type == "stdio":
            async with self._create_stdio_session() as session:
                yield session
        elif self.connection_type == "sse":
            async with self._create_sse_session() as session:
                yield session
        elif self.connection_type == "http":
            async with self._create_http_session() as session:
                yield session
        else:
            raise ValueError(f"Unsupported connection type: {self.connection_type}")

    @asynccontextmanager
    async def _create_stdio_session(self):
        """Create STDIO-based MCP session"""
        command = self.connection_config.get("command")
        args = self.connection_config.get("args", [])
        env = self.connection_config.get("env", {})

        if not command:
            raise ValueError("STDIO connection requires 'command' in connection_config")

        # Create STDIO client
        # stdio_client typically takes command and args, with env as optional keyword arg
        # Adjust signature based on actual MCP SDK version if needed
        async with mcp_stdio_client(command, args, env=env) as (read, write):  # type: ignore
            async with MCPClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()
                yield session

    @asynccontextmanager
    async def _create_sse_session(self):
        """Create SSE-based MCP session"""
        url = self.connection_config.get("url")
        headers = self.connection_config.get("headers", {})
        api_key = self.connection_config.get("api_key")

        if not url:
            raise ValueError("SSE connection requires 'url' in connection_config")

        # Add authentication header if API key provided
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Create SSE client
        async with mcp_sse_client(url, headers=headers) as (read, write):
            async with MCPClientSession(read, write) as session:
                await session.initialize()
                yield session

    @asynccontextmanager
    async def _create_http_session(self):
        """
        Create HTTP-based MCP session.
        Note: The official MCP SDK may use SSE for HTTP connections.
        For pure HTTP, we might need to use a custom transport.
        """
        url = self.connection_config.get("url")
        headers = self.connection_config.get("headers", {})
        api_key = self.connection_config.get("api_key")

        if not url:
            raise ValueError("HTTP connection requires 'url' in connection_config")

        # HTTP connections in MCP typically use SSE transport
        # If the SDK doesn't support pure HTTP, we'll use SSE
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with mcp_sse_client(url, headers=headers) as (read, write):
            async with MCPClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """
        Discover available tools from the MCP server.

        Returns:
            List of tool definitions with name, description, and inputSchema
        """
        try:
            async with self.get_session() as session:
                # List available tools
                tools_response = await session.list_tools()

                tools = []
                if hasattr(tools_response, "tools"):
                    for tool in tools_response.tools:
                        # Convert MCP Tool to our format
                        tool_name = getattr(tool, "name", "")
                        tool_description = getattr(tool, "description", "") or ""
                        tool_dict = {
                            "name": tool_name,
                            "description": tool_description,
                            "inputSchema": self._convert_tool_input_schema(tool),
                        }
                        tools.append(tool_dict)

                return tools
        except Exception as e:
            logger.error(f"Failed to discover MCP tools: {str(e)}", exc_info=True)
            raise

    async def execute_tool(
        self, tool_name: str, tool_arguments: Dict[str, Any]
    ) -> Any:
        """
        Execute a tool on the MCP server.

        Args:
            tool_name: Name of the tool to execute
            tool_arguments: Arguments for the tool

        Returns:
            Tool execution result
        """
        try:
            async with self.get_session() as session:
                # Call the tool
                result = await session.call_tool(tool_name, tool_arguments)

                # Extract content from result
                if hasattr(result, "content") and result.content:
                    # Handle different content types
                    content_list: List[Any] = []
                    for content_item in result.content:
                        if isinstance(content_item, MCPTextContent):
                            content_list.append(content_item.text)
                        elif isinstance(content_item, dict):
                            content_list.append(content_item)
                        elif hasattr(content_item, "text"):
                            # Type checker doesn't know about dynamic attributes
                            text_value = getattr(content_item, "text", str(content_item))
                            content_list.append(text_value)
                        else:
                            content_list.append(str(content_item))

                    # Return single item if only one, otherwise return list
                    if len(content_list) == 1:
                        return content_list[0]
                    return content_list

                return result
        except Exception as e:
            logger.error(
                f"Failed to execute MCP tool {tool_name}: {str(e)}", exc_info=True
            )
            raise

    def _convert_tool_input_schema(self, tool: Any) -> Dict[str, Any]:
        """
        Convert MCP Tool inputSchema to JSON Schema format.

        Args:
            tool: MCP Tool object

        Returns:
            JSON Schema dictionary
        """
        if hasattr(tool, "inputSchema") and tool.inputSchema:
            # Tool.inputSchema is already in JSON Schema format
            return tool.inputSchema

        # Fallback: create basic schema if not provided
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }


class MCPClientV2:
    """
    Enhanced MCP client using the official MCP Python SDK.
    Supports STDIO, SSE, and HTTP connection types.
    """

    def __init__(
        self,
        connection_type: Literal["stdio", "sse", "http"],
        connection_config: Dict[str, Any],
    ):
        """
        Initialize MCP client.

        Args:
            connection_type: Type of connection ("stdio", "sse", or "http")
            connection_config: Configuration dictionary with connection-specific settings:
                - For STDIO: {"command": "python", "args": ["server.py"], "env": {}}
                - For SSE/HTTP: {"url": "https://...", "api_key": "...", "headers": {}}
        """
        self.connection_manager = MCPConnectionManager(connection_type, connection_config)

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools from the MCP server."""
        return await self.connection_manager.discover_tools()

    async def execute_tool(self, tool_name: str, tool_arguments: Dict[str, Any]) -> Any:
        """Execute a tool on the MCP server."""
        return await self.connection_manager.execute_tool(tool_name, tool_arguments)
