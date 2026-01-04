"""
Simple MCP test server for testing MCP node functionality.
Supports both HTTP-based and JSON-RPC MCP protocols.

Usage:
    python -m app.modules.workflow.mcp.test_server

The server will start on http://localhost:8001
"""

import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Test Server", version="1.0.0")

# In-memory file storage for testing
file_storage: Dict[str, str] = {
    "file1.txt": "This is the content of file1.txt",
    "file2.txt": "This is the content of file2.txt",
    "file3.txt": "This is the content of file3.txt",
    "file4.txt": "This is the content of file4.txt",
    "file5.txt": "This is the content of file5.txt",
    "file6.txt": "This is the content of file6.txt",
    "file7.txt": "This is the content of file7.txt",
    "file8.txt": "This is the content of file8.txt",
    "file9.txt": "This is the content of file9.txt",
    "file10.txt": "This is the content of file10.txt",
}


class ToolCallRequest(BaseModel):
    """Request model for tool execution"""

    tool: Optional[str] = None
    toolArguments: Optional[Dict[str, Any]] = None


class JSONRPCRequest(BaseModel):
    """JSON-RPC request model"""

    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str
    params: Optional[Dict[str, Any]] = None


# Available tools definition
AVAILABLE_TOOLS = [
    {
        "name": "read_file",
        "description": "Reads a file from the filesystem",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_file",
        "description": "Writes content to a file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path where to write the file",
                },
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "Lists all files in the storage",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "delete_file",
        "description": "Deletes a file from storage",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to delete",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "echo",
        "description": "Echoes back the input message",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to echo back"}
            },
            "required": ["message"],
        },
    },
]


def validate_api_key(authorization: Optional[str] = Header(None)) -> bool:
    """Validate API key from Authorization header"""
    # For testing, accept any Bearer token or no auth
    if authorization and authorization.startswith("Bearer "):
        return True
    return True  # Allow no auth for testing


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "MCP Test Server",
        "version": "1.0.0",
        "protocols": ["http", "jsonrpc"],
        "endpoints": {"discover_tools": "/tools/list", "execute_tool": "/tools/call"},
    }


@app.post("/tools/list")
async def discover_tools_http(authorization: Optional[str] = Header(None)):
    """
    HTTP-based tool discovery endpoint.
    Returns list of available tools.
    """
    if not validate_api_key(authorization):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {"tools": AVAILABLE_TOOLS}


@app.post("/tools/call")
async def execute_tool_http(
    request: ToolCallRequest, authorization: Optional[str] = Header(None)
):
    """
    HTTP-based tool execution endpoint.
    Executes a tool with the provided arguments.
    """
    if not validate_api_key(authorization):
        raise HTTPException(status_code=401, detail="Invalid API key")

    tool_name = request.tool
    tool_arguments = request.toolArguments or {}

    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool name is required")

    # Find the tool
    tool_def = next((t for t in AVAILABLE_TOOLS if t["name"] == tool_name), None)
    if not tool_def:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. Available tools: {[t['name'] for t in AVAILABLE_TOOLS]}",
        )

    # Execute the tool
    try:
        result = await execute_tool(tool_name, tool_arguments)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@app.post("/")
@app.post("/jsonrpc")
async def jsonrpc_endpoint(request: JSONRPCRequest):
    """
    JSON-RPC endpoint for MCP protocol.
    Handles both tool discovery and execution.
    """
    method = request.method
    params = request.params or {}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request.id, "result": AVAILABLE_TOOLS}
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_arguments = params.get("toolArguments", {})

        if not tool_name:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32602, "message": "Tool name is required"},
            }

        # Find the tool
        tool_def = next((t for t in AVAILABLE_TOOLS if t["name"] == tool_name), None)
        if not tool_def:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
            }

        # Execute the tool
        try:
            result = await execute_tool(tool_name, tool_arguments)
            return {"jsonrpc": "2.0", "id": request.id, "result": {"content": result}}
        except ValueError as e:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32603, "message": str(e)},
            }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {
                    "code": -32603,
                    "message": f"Tool execution failed: {str(e)}",
                },
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }


async def execute_tool(tool_name: str, tool_arguments: Dict[str, Any]) -> Any:
    """
    Execute a tool with the provided arguments.

    Args:
        tool_name: Name of the tool to execute
        tool_arguments: Arguments for the tool

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool execution fails
    """
    if tool_name == "read_file":
        file_path = tool_arguments.get("file_path")
        if not file_path:
            raise ValueError("file_path is required")
        if file_path not in file_storage:
            raise ValueError(f"File '{file_path}' not found")
        return {"file_path": file_path, "content": file_storage[file_path]}

    elif tool_name == "write_file":
        file_path = tool_arguments.get("file_path")
        content = tool_arguments.get("content")
        if not file_path:
            raise ValueError("file_path is required")
        if content is None:
            raise ValueError("content is required")
        file_storage[file_path] = content
        return {"file_path": file_path, "status": "written", "size": len(content)}

    elif tool_name == "list_files":
        return {"files": list(file_storage.keys()), "count": len(file_storage)}

    elif tool_name == "delete_file":
        file_path = tool_arguments.get("file_path")
        if not file_path:
            raise ValueError("file_path is required")
        if file_path not in file_storage:
            raise ValueError(f"File '{file_path}' not found")
        del file_storage[file_path]
        return {"file_path": file_path, "status": "deleted"}

    elif tool_name == "echo":
        message = tool_arguments.get("message")
        if not message:
            raise ValueError("message is required")
        return {
            "echo": message,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500, content={"error": "Internal server error", "message": str(exc)}
    )


def main():
    """Run the MCP test server"""
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"

    logger.info(f"Starting MCP Test Server on http://{host}:{port}")
    logger.info(f"Available tools: {[t['name'] for t in AVAILABLE_TOOLS]}")
    logger.info("Endpoints:")
    logger.info("  - HTTP Tool Discovery: POST http://{host}:{port}/tools/list")
    logger.info("  - HTTP Tool Execution: POST http://{host}:{port}/tools/call")
    logger.info("  - JSON-RPC: POST http://{host}:{port}/jsonrpc")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main()
