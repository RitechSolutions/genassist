"""Unit tests for single-rate CRUD in LlmCostRateService"""

from uuid import uuid4

import pytest

import app.services.llm_cost_rates as rate_module
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm_cost_rate import LlmCostRateModel
from app.schemas.llm_cost_rate import LlmCostRateCreate, LlmCostRateUpdate
from app.services.llm_cost_rates import LlmCostRateService


class FakeRateRepo:
    def __init__(self, existing_by_pm=None, existing_by_id=None):
        self._by_pm = existing_by_pm
        self._by_id = existing_by_id

    async def get_active_by_provider_model(self, provider, model):
        return self._by_pm

    async def get_active_by_id(self, rate_id):
        return self._by_id

    async def create(self, obj):
        obj.id = uuid4()
        return obj

    async def update(self, obj):
        return obj


@pytest.fixture(autouse=True)
def _configure_mappers(app_def):
    return app_def


@pytest.fixture(autouse=True)
def _no_cache_calls(monkeypatch):
    monkeypatch.setattr(rate_module, "invalidate_llm_cost_rates_cache", lambda tenant=None: None)
    monkeypatch.setattr(rate_module, "get_tenant_context", lambda: "tenant-1")


@pytest.mark.asyncio
async def test_create_normalizes_and_returns_read():
    service = LlmCostRateService(FakeRateRepo(existing_by_pm=None))
    read = await service.create_rate(
        LlmCostRateCreate(provider="  OpenAI ", model=" GPT-4o ", input_per_1k=0.0025, output_per_1k=0.01)
    )
    assert read.provider_key == "openai"
    assert read.model_key == "gpt-4o"


@pytest.mark.asyncio
async def test_create_duplicate_raises_409():
    existing = LlmCostRateModel(provider_key="openai", model_key="gpt-4o", input_per_1k=0.001, output_per_1k=0.002)
    service = LlmCostRateService(FakeRateRepo(existing_by_pm=existing))
    with pytest.raises(AppException) as exc:
        await service.create_rate(
            LlmCostRateCreate(provider="openai", model="gpt-4o", input_per_1k=0.0025, output_per_1k=0.01)
        )
    assert exc.value.status_code == 409
    assert exc.value.error_key is ErrorKey.LLM_COST_RATE_ALREADY_EXISTS


@pytest.mark.asyncio
async def test_update_missing_returns_none():
    service = LlmCostRateService(FakeRateRepo(existing_by_id=None))
    result = await service.update_rate(uuid4(), LlmCostRateUpdate(input_per_1k=0.003, output_per_1k=0.009))
    assert result is None


@pytest.mark.asyncio
async def test_update_applies_new_rates():
    row = LlmCostRateModel(
        id=uuid4(), provider_key="openai", model_key="gpt-4o", input_per_1k=0.001, output_per_1k=0.002
    )
    service = LlmCostRateService(FakeRateRepo(existing_by_id=row))
    read = await service.update_rate(uuid4(), LlmCostRateUpdate(input_per_1k=0.005, output_per_1k=0.02))
    assert row.input_per_1k == 0.005 and row.output_per_1k == 0.02
    assert read.input_per_1k == 0.005
