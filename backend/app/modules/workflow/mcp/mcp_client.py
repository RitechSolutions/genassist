"""
MCP Client using the official MCP Python SDK.

Supports multiple connection types:
- STDIO: For local MCP servers running as processes
- HTTP/SSE: For remote MCP servers over HTTP/HTTPS

Authentication (HTTP/SSE only):
- api_key  : static Bearer token  (auth_type="api_key" or omitted)
- oauth2   : OAuth2 Client Credentials / OIDC  (auth_type="oauth2")
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

import httpx
from mcp import ClientSession as MCPClientSession
from mcp.client.sse import sse_client as mcp_sse_client
from mcp.client.stdio import stdio_client as mcp_stdio_client
from mcp.client.streamable_http import streamable_http_client as mcp_streamablehttp_client
from mcp.types import TextContent as MCPTextContent

from app.modules.workflow.mcp.oauth2_client import get_oauth2_token

logger = logging.getLogger(__name__)


def _normalize_bearer_secret(value: str) -> str:
    """Strip whitespace and a single leading 'Bearer ' prefix (common paste mistake)."""
    raw = (value or "").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].lstrip()
    return raw


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

    async def _resolve_auth_header(self) -> Optional[str]:
        """
        Return the value for the Authorization header based on auth_type.

        - auth_type "api_key" (or absent): use api_key field as Bearer token
        - auth_type "oauth2" (and common aliases like "oauth2.0", "oidc"):
            fetch token via OAuth2/OIDC (client credentials)
        - auth_type "none"               : no Authorization header
        """
        def _coerce_auth_type(value: Any) -> str:
            raw = str(value or "").strip().lower()
            if not raw:
                return "api_key"
            # Accept common variants that show up in UIs / configs.
            if raw in {"oauth2.0", "oauth2_0", "oauth2-0", "oauth2"}:
                return "oauth2"
            if raw in {"oidc", "openid", "openidconnect", "open_id_connect", "open-id-connect"}:
                return "oauth2"
            if raw in {"apikey", "api-key", "api_key"}:
                return "api_key"
            return raw

        def _merged_oauth2_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
            """
            Normalize OAuth2 config shape for get_oauth2_token().

            Supports:
            - top-level oauth2_* keys (used by MCP node dialog)
            - nested auth_values.oauth2_* (used by some persisted configs)
            - camelCase keys from some clients
            """
            merged: Dict[str, Any] = dict(cfg)

            av = merged.get("auth_values")
            if isinstance(av, dict):
                # Only merge non-empty values to avoid clobbering explicit top-level settings.
                for k, v in av.items():
                    if k not in merged and v is not None:
                        merged[k] = v

            # camelCase → snake_case aliases
            alias_map = {
                "oauth2ClientId": "oauth2_client_id",
                "oauth2ClientSecret": "oauth2_client_secret",
                "oauth2TokenUrl": "oauth2_token_url",
                "oauth2IssuerUrl": "oauth2_issuer_url",
                "oauth2Scopes": "oauth2_scopes",
                "oauth2Audience": "oauth2_audience",
                "oauth2Flow": "oauth2_flow",
            }
            for src, dst in alias_map.items():
                if dst not in merged and src in merged:
                    merged[dst] = merged.get(src)

            return merged

        auth_type = _coerce_auth_type(self.connection_config.get("auth_type", "api_key"))

        if auth_type == "none":
            return None

        if auth_type == "oauth2":
            oauth_cfg = _merged_oauth2_config(self.connection_config)
            token = await get_oauth2_token(oauth_cfg)
            token_norm = _normalize_bearer_secret(token)
            if not token_norm:
                raise ValueError("OAuth2 token response was empty")
            return f"Bearer {token_norm}"

        # Default: static api_key
        api_key: Optional[str] = self.connection_config.get("api_key")
        if api_key:
            key_norm = _normalize_bearer_secret(api_key)
            if key_norm:
                return f"Bearer {key_norm}"
        return None

    @asynccontextmanager
    async def _create_sse_session(self):
        """Create SSE-based MCP session"""
        url = self.connection_config.get("url")
        headers: Dict[str, Any] = dict(self.connection_config.get("headers") or {})

        if not url:
            raise ValueError("SSE connection requires 'url' in connection_config")

        auth_header = await self._resolve_auth_header()
        if auth_header:
            headers["Authorization"] = auth_header

        # Create SSE client
        async with mcp_sse_client(url, headers=headers) as (read, write):
            async with MCPClientSession(read, write) as session:
                await session.initialize()
                yield session

    @asynccontextmanager
    async def _create_http_session(self):
        """
        Create Streamable HTTP-based MCP session (MCP 2025 spec).
        Uses POST requests, which is required by servers implementing the
        Streamable HTTP transport (as opposed to the older SSE transport).
        """
        url = self.connection_config.get("url")
        headers: Dict[str, Any] = dict(self.connection_config.get("headers") or {})

        if not url:
            raise ValueError("HTTP connection requires 'url' in connection_config")

        auth_header = await self._resolve_auth_header()
        if auth_header:
            headers["Authorization"] = auth_header

        # Use AsyncClient as a context manager so the transport opens correctly; the MCP SDK
        # does not enter a caller-provided client (see streamable_http_client client_provided).
        timeout = httpx.Timeout(30.0, read=300.0)
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as http_client:
            async with mcp_streamablehttp_client(url, http_client=http_client) as (read, write, _):
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
