"""
MCP (Model Context Protocol) API endpoints for discovering and managing MCP tools.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from pydantic import BaseModel, Field, ConfigDict
from starlette.responses import Response as StarletteResponse
from app.core.permissions.constants import Permissions as P
from app.auth.dependencies import auth, permissions
from app.modules.workflow.mcp.mcp_client import MCPClientV2
from app.modules.workflow.mcp.mcp_server_adapter import WorkflowMCPServerAdapter
from app.services.mcp_server import MCPServerService
from app.repositories.workflow import WorkflowRepository
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.dependencies.injector import injector
from fastapi_injector import Injected
from mcp.types import TextContent
from mcp.server import Server
from mcp.server.sse import SseServerTransport

logger = logging.getLogger(__name__)

router = APIRouter()


class DiscoverToolsRequest(BaseModel):
    """Request model for discovering MCP tools"""
    connection_type: str = Field(..., description="Connection type: 'stdio', 'sse', or 'http'")
    connection_config: Dict[str, Any] = Field(..., description="Connection configuration")


class MCPTool(BaseModel):
    """MCP tool definition"""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputSchema: Optional[Dict[str, Any]] = Field(None, description="JSON schema defining tool parameters")


class DiscoverToolsResponse(BaseModel):
    """Response model for tool discovery"""
    tools: list[MCPTool] = Field(..., description="List of available tools from the MCP server")


@router.post(
    "/discover-tools",
    response_model=DiscoverToolsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(auth), Depends(permissions(P.Workflow.TEST))],
)
async def discover_mcp_tools(request: DiscoverToolsRequest) -> DiscoverToolsResponse:
    """
    Discover available tools from an MCP server using the official MCP SDK.

    This endpoint connects to an MCP server and retrieves the list of available tools.
    Supports STDIO, SSE, and HTTP connection types.

    Args:
        request: Request containing connection type and configuration

    Returns:
        Response containing list of available tools

    Raises:
        HTTPException: If tool discovery fails
    """
    try:
        # Validate connection type and create client
        connection_type_raw = request.connection_type
        if connection_type_raw not in ("stdio", "sse", "http"):
            raise ValueError(
                f"Invalid connection_type: {connection_type_raw}. Must be one of: 'stdio', 'sse', 'http'"
            )

        # Type narrowing for MCP SDK - use explicit if/elif to help type checker
        from typing import Literal
        if connection_type_raw == "stdio":
            connection_type: Literal["stdio", "sse", "http"] = "stdio"
        elif connection_type_raw == "sse":
            connection_type = "sse"
        else:  # Must be "http" after validation
            connection_type = "http"

        # Create MCP client using official SDK
        # Type checker doesn't narrow properly, but we've validated the value above
        mcp_client = MCPClientV2(connection_type, request.connection_config)  # type: ignore[arg-type]

        # Discover tools
        tools_data = await mcp_client.discover_tools()

        # Convert to response format
        tools = []
        for tool_data in tools_data:
            if isinstance(tool_data, dict):
                tool = MCPTool(
                    name=tool_data.get("name", ""),
                    description=tool_data.get("description", ""),
                    inputSchema=tool_data.get("inputSchema") or tool_data.get("input_schema")
                )
                tools.append(tool)
            else:
                logger.warning(f"Unexpected tool data format: {tool_data}")

        return DiscoverToolsResponse(tools=tools)

    except ValueError as e:
        # Validation errors (e.g., invalid URL, authentication failure)
        logger.error(f"MCP tool discovery failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Connection errors, timeouts, etc.
        logger.error(f"Error discovering MCP tools: {str(e)}", exc_info=True)
        error_message = f"Failed to connect to MCP server: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )


def extract_bearer_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization


class JSONRPCRequest(BaseModel):
    """JSON-RPC request model"""
    jsonrpc: str = Field("2.0", description="JSON-RPC version")
    id: Optional[Any] = Field(None, description="Request ID")
    method: str = Field(..., description="Method name (e.g., 'tools/list', 'tools/call')")
    params: Optional[Dict[str, Any]] = Field(None, description="Method parameters")


class JSONRPCResponse(BaseModel):
    """JSON-RPC response model"""
    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Optional[Any] = Field(default=None, description="Request ID")
    result: Optional[Any] = Field(default=None, description="Method result")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error information")
    
    model_config = ConfigDict(extra="forbid")


class MCPToolCallRequest(BaseModel):
    """Request model for calling an MCP tool"""
    tool: str = Field(..., description="Tool name to execute")
    arguments: Optional[Dict[str, Any]] = Field(None, description="Tool arguments")
    
    def get_arguments(self) -> Dict[str, Any]:
        """Get arguments"""
        return self.arguments or {}


class MCPToolCallResponse(BaseModel):
    """Response model for tool execution"""
    output: Dict[str, Any] = Field(..., description="Tool execution output")


async def _handle_jsonrpc_internal(
    request: JSONRPCRequest,
    authorization: Optional[str],
    mcp_server_service: MCPServerService,
) -> JSONRPCResponse:
    """
    Internal handler for JSON-RPC requests.
    
    Supports:
    - tools/list: List available tools
    - tools/call: Execute a tool
    """
    try:
        # Extract API key from Authorization header
        api_key = extract_bearer_token(authorization)
        if not api_key:
            return JSONRPCResponse(
                jsonrpc="2.0",
                id=request.id,
                result=None,
                error={
                    "code": -32001,
                    "message": "Missing API key in Authorization header"
                }
            )

        # Validate API key and get MCP server
        mcp_server = await mcp_server_service.validate_api_key(api_key)
        if not mcp_server:
            return JSONRPCResponse(
                jsonrpc="2.0",
                id=request.id,
                result=None,
                error={
                    "code": -32001,
                    "message": "Invalid API key"
                }
            )

        # Check if server is active
        if mcp_server.is_active != 1:
            return JSONRPCResponse(
                jsonrpc="2.0",
                id=request.id,
                result=None,
                error={
                    "code": -32002,
                    "message": "MCP server is inactive"
                }
            )

        # Route based on method
        if request.method == "tools/list":
            # List tools using MCP SDK adapter
            workflow_repo = injector.get(WorkflowRepository)
            workflow_engine = WorkflowEngine.get_instance()
            
            adapter = WorkflowMCPServerAdapter(
                mcp_server, workflow_repo, workflow_engine
            )
            mcp_tools = await adapter.list_tools()
            
            # Convert MCP Tool objects to dict format for JSON-RPC response
            tools_list = []
            for tool in mcp_tools:
                tools_list.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema or {},
                })
            
            return JSONRPCResponse(
                jsonrpc="2.0",
                id=request.id,
                result=tools_list,
                error=None
            )

        elif request.method == "tools/call":
            # Execute tool using MCP SDK adapter
            params = request.params or {}
            tool_name = params.get("name")
            tool_arguments = params.get("arguments") or {}

            if not tool_name:
                return JSONRPCResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    result=None,
                    error={
                        "code": -32602,
                        "message": "Missing 'name' parameter in params"
                    }
                )

            try:
                workflow_repo = injector.get(WorkflowRepository)
                workflow_engine = WorkflowEngine.get_instance()
                
                adapter = WorkflowMCPServerAdapter(
                    mcp_server, workflow_repo, workflow_engine
                )
                
                # Call tool using MCP SDK adapter
                # Note: adapter.call_tool returns List[TextContent], not CallToolResult
                # (The server decorator wraps it in CallToolResult, but we're calling it directly)
                content_list_result = await adapter.call_tool(tool_name, tool_arguments)
                
                # Convert List[TextContent] to JSON-RPC format
                content_list = []
                for content_item in content_list_result:
                    if isinstance(content_item, TextContent):
                        content_list.append({"type": "text", "text": content_item.text})
                    elif isinstance(content_item, dict):
                        content_list.append(content_item)
                    else:
                        content_list.append({"type": "text", "text": str(content_item)})
                
                result_data = {
                    "content": content_list,
                    "isError": False,  # No error if we got here
                }
                
                return JSONRPCResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    result=result_data,
                    error=None
                )

            except ValueError as e:
                # Tool not found or validation error
                return JSONRPCResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    result=None,
                    error={
                        "code": -32601,
                        "message": str(e)
                    }
                )
            except Exception as e:
                logger.error(f"Error executing MCP tool '{tool_name}': {e}", exc_info=True)
                return JSONRPCResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    result=None,
                    error={
                        "code": -32603,
                        "message": f"Workflow execution failed: {str(e)}"
                    }
                )

        else:
            # Unknown method
            return JSONRPCResponse(
                jsonrpc="2.0",
                id=request.id,
                result=None,
                error={
                    "code": -32601,
                    "message": f"Unknown method: {request.method}"
                }
            )

    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}", exc_info=True)
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=request.id if hasattr(request, 'id') else None,
            result=None,
            error={
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        )


@router.post("/jsonrpc", response_model=JSONRPCResponse)
async def handle_jsonrpc_jsonrpc(
    request: JSONRPCRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
):
    """
    Handle JSON-RPC requests at /jsonrpc endpoint.
    """
    return await _handle_jsonrpc_internal(request, authorization, mcp_server_service)


@router.get("/")
async def handle_root_get(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
):
    """
    Handle GET requests at root endpoint for SSE connections.
    
    This allows the MCP SDK's SSE client to connect to the base URL.
    """
    # Check if this is an SSE request (Accept header contains text/event-stream)
    accept_header = request.headers.get("Accept", "")
    if "text/event-stream" in accept_header:
        # Route to SSE handler
        return await handle_sse(request, authorization, mcp_server_service)
    else:
        # Not an SSE request, return 405 Method Not Allowed
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="GET requests are only supported for SSE connections. Use POST for JSON-RPC."
        )


@router.post("", response_model=JSONRPCResponse)
async def handle_jsonrpc_root(
    request: JSONRPCRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
):
    """
    Handle JSON-RPC requests at root endpoint.
    """
    return await _handle_jsonrpc_internal(request, authorization, mcp_server_service)


# SSE transport instance (shared across requests)
_sse_transport: Optional[SseServerTransport] = None


def get_sse_transport() -> SseServerTransport:
    """Get or create SSE transport instance."""
    global _sse_transport
    if _sse_transport is None:
        # Use relative path - FastAPI will combine with router prefix (/api/mcp)
        _sse_transport = SseServerTransport("/messages/")
    return _sse_transport


def ensure_root_path_in_scope(scope: Any, prefix: str) -> Dict[str, Any]:
    """Ensure root_path is set correctly in scope for SSE transport."""
    # FastAPI/Starlette should set root_path automatically when mounting routers,
    # but we ensure it's set correctly here
    # We need to create a new dict since scope might be a read-only mapping
    new_scope = dict(scope)
    # Set root_path if not already set or if it's empty
    if not new_scope.get("root_path"):
        new_scope["root_path"] = prefix
    return new_scope


@router.get("/sse", include_in_schema=False)
async def handle_sse(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
) -> None:
    """
    Handle SSE (Server-Sent Events) connections for MCP protocol.
    
    This endpoint supports GET requests and streams Server-Sent Events
    as required by the MCP SDK's SSE client.
    
    Note: The SSE transport handles sending the response directly via ASGI,
    so this function returns None.
    """
    # Extract API key from Authorization header
    api_key = extract_bearer_token(authorization)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key in Authorization header"
        )

    # Validate API key and get MCP server
    mcp_server = await mcp_server_service.validate_api_key(api_key)
    if not mcp_server:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Check if server is active
    if mcp_server.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP server is inactive"
        )

    # Create MCP server instance
    workflow_repo = injector.get(WorkflowRepository)
    workflow_engine = WorkflowEngine.get_instance()
    
    adapter = WorkflowMCPServerAdapter(mcp_server, workflow_repo, workflow_engine)
    
    # Create server instance
    server = Server("workflow-mcp-server")
    
    @server.list_tools()
    async def list_tools():
        """List available tools."""
        return await adapter.list_tools()
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]):
        """Execute a tool."""
        return await adapter.call_tool(name, arguments)
    
    # Get SSE transport and handle the connection
    transport = get_sse_transport()
    
    # Ensure root_path is set correctly in scope for the transport
    # Extract root_path from request path - if request is to /api/mcp/sse, root_path should be /api/mcp
    request_path = request.url.path
    # Remove the endpoint path (/sse) to get the root_path
    root_path = request_path.rsplit("/sse", 1)[0] if "/sse" in request_path else "/api/mcp"
    scope = ensure_root_path_in_scope(request.scope, root_path)
    
    # Use SSE transport's connect_sse method
    # The transport handles sending the response directly via request._send
    # so we don't return anything from this function
    async with transport.connect_sse(
        scope, request.receive, request._send
    ) as streams:
        read_stream, write_stream = streams
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )
    
    # The SSE transport has already sent the response via ASGI
    # We return None to indicate the response was handled by the transport
    return None


@router.post("/messages", include_in_schema=False)
async def handle_sse_messages(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
) -> None:
    """
    Handle POST messages for SSE transport.
    
    This endpoint receives client messages that link to a previously-established SSE session.
    Note: This endpoint uses an ASGI app that handles the response directly.
    """
    # Extract API key from Authorization header
    api_key = extract_bearer_token(authorization)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key in Authorization header"
        )

    # Validate API key and get MCP server
    mcp_server = await mcp_server_service.validate_api_key(api_key)
    if not mcp_server:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Check if server is active
    if mcp_server.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP server is inactive"
        )

    # Get SSE transport and handle POST message as ASGI app
    transport = get_sse_transport()
    # Extract root_path from request path - if request is to /api/mcp/messages/, root_path should be /api/mcp
    request_path = request.url.path
    # Remove the endpoint path (/messages/) to get the root_path
    root_path = request_path.rsplit("/messages", 1)[0] if "/messages/" in request_path else "/api/mcp"
    scope = ensure_root_path_in_scope(request.scope, root_path)
    
    # Call the ASGI app directly - it handles sending the response itself
    # The ASGI app will call send() to send the response (202 Accepted)
    # handle_post_message expects (scope, receive, send) where send is an ASGI send function
    # The send function signature: async def send(message: MutableMapping[str, Any]) -> None
    from collections.abc import MutableMapping
    
    # Track if response was sent to prevent FastAPI from sending another
    response_sent = False
    
    async def asgi_send(message: MutableMapping[str, Any]) -> None:
        """ASGI send function that forwards to request._send"""
        nonlocal response_sent
        if message.get("type") == "http.response.start":
            response_sent = True
        # Convert MutableMapping to dict for request._send if needed
        msg_dict = dict(message) if not isinstance(message, dict) else message
        await request._send(msg_dict)
    
    await transport.handle_post_message(
        scope, request.receive, asgi_send  # type: ignore[arg-type]
    )
    
    # The ASGI app has already sent the response (202 Accepted) via asgi_send
    # Return None to prevent FastAPI from trying to send another response
    # The response was already sent by the ASGI app, so FastAPI middleware
    # should not try to process a return value
    # Note: This may still cause an error in middleware, but the response
    # was successfully sent by the ASGI app
    return None


async def _list_mcp_tools_internal(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
) -> Dict[str, Any]:
    """
    Internal function to list MCP tools.
    Used by both GET /tools and POST /tools/list endpoints.
    """
    # Extract API key from Authorization header
    api_key = extract_bearer_token(authorization)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key in Authorization header"
        )

    # Validate API key and get MCP server
    mcp_server = await mcp_server_service.validate_api_key(api_key)
    if not mcp_server:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Check if server is active
    if mcp_server.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP server is inactive"
        )

    # Build tools list using MCP SDK adapter
    workflow_repo = injector.get(WorkflowRepository)
    workflow_engine = WorkflowEngine.get_instance()
    
    adapter = WorkflowMCPServerAdapter(
        mcp_server, workflow_repo, workflow_engine
    )
    mcp_tools = await adapter.list_tools()
    
    # Convert MCP Tool objects to dict format
    tools_list = []
    for tool in mcp_tools:
        tools_list.append({
            "name": tool.name,
            "description": tool.description or "",
            "inputSchema": tool.inputSchema or {},
        })

    return {"tools": tools_list}


@router.get("/tools", response_model=Dict[str, Any])
async def list_mcp_tools_get(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
):
    """
    List available tools from active MCP servers (MCP Protocol endpoint - GET).
    
    Authenticates using API key from Authorization header and returns all tools
    exposed by the authenticated MCP server.
    """
    return await _list_mcp_tools_internal(authorization, mcp_server_service)


@router.post("/tools/list", response_model=Dict[str, Any])
async def list_mcp_tools_post(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
):
    """
    List available tools from active MCP servers (MCP Protocol endpoint - POST).
    
    This endpoint matches the MCP client's expected format for tool discovery.
    Authenticates using API key from Authorization header and returns all tools
    exposed by the authenticated MCP server.
    """
    return await _list_mcp_tools_internal(authorization, mcp_server_service)


@router.post("/tools/call", response_model=MCPToolCallResponse)
async def execute_mcp_tool(
    request: MCPToolCallRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    mcp_server_service: MCPServerService = Injected(MCPServerService),
):
    """
    Execute a workflow as an MCP tool (MCP Protocol endpoint).
    
    Authenticates using API key, finds the tool in the server's workflows,
    validates arguments, and executes the workflow.
    """
    # Extract API key from Authorization header
    api_key = extract_bearer_token(authorization)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key in Authorization header"
        )

    # Validate API key and get MCP server
    mcp_server = await mcp_server_service.validate_api_key(api_key)
    if not mcp_server:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Check if server is active
    if mcp_server.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP server is inactive"
        )

    try:
        # Use MCP SDK adapter for tool execution
        workflow_repo = injector.get(WorkflowRepository)
        workflow_engine = WorkflowEngine.get_instance()
        
        adapter = WorkflowMCPServerAdapter(
            mcp_server, workflow_repo, workflow_engine
        )
        
        # Get arguments
        input_data = request.get_arguments()
        
        # Call tool using MCP SDK adapter
        # Note: adapter.call_tool returns List[TextContent], not CallToolResult
        # (The server decorator wraps it in CallToolResult, but we're calling it directly)
        content_list_result = await adapter.call_tool(request.tool, input_data)
        
        # Extract content from List[TextContent]
        # For HTTP endpoint, we return the first text content as output
        output = {}
        if content_list_result:
            for content_item in content_list_result:
                if isinstance(content_item, TextContent):
                    import json
                    try:
                        output = json.loads(content_item.text)
                    except json.JSONDecodeError:
                        output = {"text": content_item.text}
                    break
        
        return MCPToolCallResponse(output=output)

    except HTTPException:
        raise
    except ValueError as e:
        # Tool not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error executing MCP tool '{request.tool}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {str(e)}"
        )

