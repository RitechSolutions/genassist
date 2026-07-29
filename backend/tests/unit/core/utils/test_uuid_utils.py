"""Unit tests for the shared UUID coercion helper"""

from uuid import uuid4

from app.core.utils.uuid_utils import coerce_uuid


class TestCoerceUuid:
    def test_passthrough_uuid(self):
        u = uuid4()
        assert coerce_uuid(u) is u

    def test_string_uuid(self):
        u = uuid4()
        assert coerce_uuid(str(u)) == u

    def test_none(self):
        assert coerce_uuid(None) is None

    def test_garbage_returns_none(self):
        assert coerce_uuid("not-a-uuid") is None
        assert coerce_uuid("mcp_tool_abc") is None
        assert coerce_uuid(12345) is None
