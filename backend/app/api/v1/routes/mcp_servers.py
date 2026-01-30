from fastapi import APIRouter, Depends, HTTPException, status, Request
from uuid import UUID
from typing import List

from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerResponse,
)
from app.services.mcp_server import MCPServerService
from app.auth.dependencies import auth
from app.core.exceptions.exception_classes import AppException
from fastapi_injector import Injected

router = APIRouter(tags=["MCP Servers"], dependencies=[Depends(auth)])


@router.post("", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    data: MCPServerCreate,
    request: Request,
    service: MCPServerService = Injected(MCPServerService),
):
    """Create a new MCP server."""
    try:
        return await service.create(data, request)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.error_detail or str(e.error_key))


@router.get("", response_model=List[MCPServerResponse])
async def list_mcp_servers(
    request: Request,
    service: MCPServerService = Injected(MCPServerService),
):
    """Get all MCP servers for the current user."""
    try:
        return await service.get_all(request)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.error_detail or str(e.error_key))


@router.get("/{mcp_server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    mcp_server_id: UUID,
    request: Request,
    service: MCPServerService = Injected(MCPServerService),
):
    """Get an MCP server by ID."""
    try:
        return await service.get_by_id(mcp_server_id, request)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.error_detail or str(e.error_key))


@router.put("/{mcp_server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    mcp_server_id: UUID,
    data: MCPServerUpdate,
    request: Request,
    service: MCPServerService = Injected(MCPServerService),
):
    """Update an MCP server."""
    try:
        return await service.update(mcp_server_id, data, request)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.error_detail or str(e.error_key))


@router.delete(
    "/{mcp_server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_mcp_server(
    mcp_server_id: UUID,
    service: MCPServerService = Injected(MCPServerService),
):
    """Delete an MCP server (soft delete)."""
    try:
        deleted = await service.delete(mcp_server_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="MCP server not found")
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.error_detail or str(e.error_key))

