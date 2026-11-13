from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routes.auth import me
from app.core.tenant_scope import set_tenant_context


@pytest.mark.asyncio
@pytest.mark.parametrize("tenant,expected", [("master", True), ("acme", False)])
async def test_me_reports_whether_the_request_runs_in_the_master_tenant(tenant, expected):
    set_tenant_context(tenant)
    details = SimpleNamespace(id=uuid4(), username="u", email="u@example.com", permissions=["*"], roles=[])
    user_service = SimpleNamespace(get_by_id_for_auth=AsyncMock(return_value=details))

    result = await me(user=SimpleNamespace(id=details.id, force_upd_pass_date=None), user_service=user_service)

    assert result["is_master_tenant"] is expected
