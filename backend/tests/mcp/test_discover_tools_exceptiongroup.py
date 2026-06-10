"""ExceptionGroup handling for /mcp/discover-tools (MCP SDK TaskGroup wraps McpError)."""

from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from app.api.v1.routes.mcp import _first_mcp_error_or_leaf


def test_first_mcp_error_returns_nested_mcp_error():
    inner = McpError(ErrorData(code=-32001, message="Invalid API key", data=None))
    eg = ExceptionGroup("tg", [inner])
    assert _first_mcp_error_or_leaf(eg) is inner


def test_first_mcp_error_nested_exception_group():
    inner = McpError(ErrorData(code=-1, message="bad", data=None))
    eg = ExceptionGroup("outer", [ExceptionGroup("inner", [inner])])
    assert _first_mcp_error_or_leaf(eg) is inner


def test_first_mcp_error_no_mcp_returns_leaf():
    leaf = ValueError("no mcp")
    eg = ExceptionGroup("tg", [leaf])
    assert _first_mcp_error_or_leaf(eg) is leaf


def test_first_mcp_error_plain_mcp_error():
    err = McpError(ErrorData(code=0, message="x", data=None))
    assert _first_mcp_error_or_leaf(err) is err
