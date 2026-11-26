"""Template Marketplace access: the feature flag guards every template route."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from sqlalchemy.dialects import postgresql

from app.api.v1.routes import templates as template_routes
from app.auth.dependencies import auth
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.seed.seed import seed_feature_flags
from app.repositories.agent import AgentRepository
from app.repositories.feature_flag import FeatureFlagRepository
from app.schemas.filter import BaseFilterModel
from app.services.agent_config import AgentConfigService
from app.services.feature_flag import TEMPLATE_MARKETPLACE_FLAG, FeatureFlagService


def _flags(row):
    repo = AsyncMock(spec=FeatureFlagRepository)
    repo.get_by_key.return_value = row
    return FeatureFlagService(repo=repo)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row, enabled",
    [
        (None, False),
        (SimpleNamespace(is_active=1, val="false"), False),
        (SimpleNamespace(is_active=0, val="true"), False),
        (SimpleNamespace(is_active=1, val="True"), False),
        (SimpleNamespace(is_active=1, val="true"), True),
        (SimpleNamespace(is_active=2, val="true"), True),
    ],
)
async def test_the_flag_is_on_only_when_its_row_is_active_and_true(row, enabled):
    assert await _flags(row).is_enabled(TEMPLATE_MARKETPLACE_FLAG) is enabled


def test_every_template_route_checks_sign_in_and_then_the_flag():
    routes = [route for route in template_routes.router.routes if isinstance(route, APIRoute)]
    assert len(routes) >= 10
    for route in routes:
        first_two = [depends.dependency for depends in route.dependencies[:2]]
        assert first_two == [auth, template_routes.require_template_marketplace], route.path


@pytest.mark.asyncio
async def test_a_turned_off_flag_answers_403():
    with pytest.raises(AppException) as exc:
        await template_routes.require_template_marketplace(flags=_flags(None))
    assert exc.value.status_code == 403
    assert exc.value.error_key == ErrorKey.TEMPLATE_MARKETPLACE_DISABLED

    await template_routes.require_template_marketplace(flags=_flags(SimpleNamespace(is_active=1, val="true")))


@pytest.mark.asyncio
async def test_new_tenants_get_the_flag_row_turned_off():
    session = AsyncMock()
    await seed_feature_flags(session)

    compiled = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "ON CONFLICT (key) DO NOTHING" in str(compiled)
    assert compiled.params["key"] == TEMPLATE_MARKETPLACE_FLAG
    assert (compiled.params["val"], compiled.params["is_active"]) == ("false", 1)
    session.commit.assert_awaited_once()


def _agent_row(created_by):
    return SimpleNamespace(
        id=uuid4(),
        name="Support",
        workflow_id=uuid4(),
        possible_queries="",
        is_active=1,
        is_system=False,
        created_by=created_by,
    )


@pytest.mark.asyncio
async def test_agent_list_items_say_whether_the_user_created_them():
    me, colleague = uuid4(), uuid4()
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalar=MagicMock(return_value=2)),
            MagicMock(all=MagicMock(return_value=[_agent_row(me), _agent_row(colleague)])),
        ]
    )
    service = AgentConfigService(
        repository=AgentRepository(db),
        operator_service=MagicMock(),
        workflow_service=MagicMock(),
        user_types_repository=MagicMock(),
        db=db,
    )

    page = await service.get_list_paginated(BaseFilterModel(), user_id=me)

    selected = {column.name for column in db.execute.call_args_list[1].args[0].selected_columns}
    assert "created_by" in selected
    assert [item.is_mine for item in page.items] == [True, False]
    # The creator's id stays on the server.
    assert all("created_by" not in item.model_dump() for item in page.items)
