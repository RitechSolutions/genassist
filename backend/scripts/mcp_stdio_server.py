#!/usr/bin/env python3
"""
MCP Server entry point for stdio transport (for Cursor and other MCP clients).

This script runs an MCP server that exposes workflows as tools via stdio.
It can be configured via environment variables or command-line arguments.

Usage:
    python scripts/mcp_stdio_server.py --api-key <api_key>

Environment Variables:
    MCP_API_KEY: API key for authentication
    MCP_SERVER_NAME: Name of the MCP server (default: "workflow-mcp-server")
"""

import asyncio
import logging
import sys
import os
import argparse
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.stdio import stdio_server
from mcp.server import Server
from app.repositories.workflow import WorkflowRepository
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.mcp.mcp_server_adapter import WorkflowMCPServerAdapter
from app.db.multi_tenant_session import multi_tenant_manager
from app.repositories.mcp_server import MCPServerRepository
from app.auth.utils import hash_api_key
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.db.models.mcp_server import MCPServerModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_mcp_server_by_api_key(api_key: str):
    """Get MCP server by API key."""
    # Initialize multi-tenant manager if needed
    await multi_tenant_manager.initialize()
    
    # Get session factory for master tenant
    session_factory = multi_tenant_manager.get_tenant_session_factory("master")
    
    async with session_factory() as session:
        try:
            # Get MCP server by API key hash
            api_key_hash = hash_api_key(api_key)
            repo = MCPServerRepository(session)
            mcp_server_model = await repo.get_by_api_key_hash(api_key_hash)
            
            if not mcp_server_model or mcp_server_model.is_active != 1:
                return None
            
            # Load workflows with relationships
            result = await session.execute(
                select(MCPServerModel)
                .options(selectinload(MCPServerModel.workflows))
                .where(MCPServerModel.id == mcp_server_model.id)
            )
            mcp_server_model = result.scalar_one_or_none()
            
            if not mcp_server_model:
                return None
            
            # Convert to response format manually
            workflows = []
            workflow_repo = WorkflowRepository(session)
            for wf in mcp_server_model.workflows:
                workflow_model = await workflow_repo.get_by_id(wf.workflow_id)
                if workflow_model:
                    from app.services.mcp_server import _extract_input_schema_from_chat_input_node
                    input_schema = _extract_input_schema_from_chat_input_node(workflow_model)
                    from app.schemas.mcp_server import MCPServerWorkflowResponse
                    workflows.append(
                        MCPServerWorkflowResponse(
                            id=wf.id,
                            mcp_server_id=wf.mcp_server_id,
                            workflow_id=wf.workflow_id,
                            tool_name=wf.tool_name,
                            tool_description=wf.tool_description,
                            input_schema=input_schema,
                            created_at=wf.created_at,
                            updated_at=wf.updated_at,
                        )
                    )
            
            # Create a simple response-like object
            class MCPServerResponseObj:
                def __init__(self, model, workflows_list):
                    self.id = model.id
                    self.name = model.name
                    self.workflows = workflows_list
                    self.is_active = model.is_active
            
            return MCPServerResponseObj(mcp_server_model, workflows)
        except Exception as e:
            logger.error(f"Error getting MCP server: {e}", exc_info=True)
            return None


async def main():
    """Main entry point for stdio MCP server."""
    parser = argparse.ArgumentParser(description="MCP Server for stdio transport")
    parser.add_argument("--api-key", help="API key for authentication", default=os.getenv("MCP_API_KEY"))
    parser.add_argument("--server-name", help="Server name", default=os.getenv("MCP_SERVER_NAME", "workflow-mcp-server"))
    
    args = parser.parse_args()
    
    if not args.api_key:
        logger.error("API key is required. Set MCP_API_KEY environment variable or use --api-key")
        sys.exit(1)
    
    # Get MCP server by API key
    mcp_server = await get_mcp_server_by_api_key(args.api_key)
    if not mcp_server:
        logger.error("Invalid API key or server not found")
        sys.exit(1)
    
    # Get session factory for workflow operations
    session_factory = multi_tenant_manager.get_tenant_session_factory("master")
    
    # Create MCP server instance using MCP SDK
    server = Server(args.server_name)
    
    @server.list_tools()
    async def list_tools():
        """List available tools."""
        async with session_factory() as session:
            workflow_repo = WorkflowRepository(session)
            adapter = WorkflowMCPServerAdapter(mcp_server, workflow_repo)
            return await adapter.list_tools()
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]):
        """Execute a tool."""
        async with session_factory() as session:
            workflow_repo = WorkflowRepository(session)
            adapter = WorkflowMCPServerAdapter(mcp_server, workflow_repo)
            return await adapter.call_tool(name, arguments)
    
    # Run stdio server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

