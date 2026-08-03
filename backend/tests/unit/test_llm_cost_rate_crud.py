"""Unit tests for single-rate CRUD in LlmCostRateService"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

import app.services.llm_cost_rates as rate_module
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm_cost_rate import LlmCostRateModel
from app.schemas.llm_cost_rate import LlmCostRateCreate, LlmCostRateRead, LlmCostRateUpdate
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
    read = await service.update_rate(uuid4(), LlmCostRateUpdate(input_per_1k="0.005", output_per_1k="0.02"))
    assert row.input_per_1k == Decimal("0.005") and row.output_per_1k == Decimal("0.02")
    assert read.input_per_1k == Decimal("0.005")


@pytest.mark.asyncio
async def test_create_keeps_small_rates_exact():
    service = LlmCostRateService(FakeRateRepo(existing_by_pm=None))
    read = await service.create_rate(
        LlmCostRateCreate(provider="openai", model="gpt-4o-mini", input_per_1k="0.00015", output_per_1k="0.0000001")
    )
    assert read.input_per_1k == Decimal("0.00015")
    assert read.output_per_1k == Decimal("0.0000001")


def test_read_serializes_rates_without_truncation():
    read = LlmCostRateRead(
        id=uuid4(),
        provider_key="openai",
        model_key="gpt-4o-mini",
        input_per_1k=Decimal("0.00015"),
        output_per_1k=Decimal("0.0000001"),
        updated_at=datetime.now(timezone.utc),
    )
    dumped = read.model_dump(mode="json")
    assert dumped["input_per_1k"] == "0.00015"
    assert dumped["output_per_1k"] == "0.0000001"


def test_read_serializes_zero_and_trailing_zeros_plainly():
    read = LlmCostRateRead(
        id=uuid4(),
        provider_key="vllm",
        model_key="local",
        input_per_1k=Decimal("0.000000"),
        output_per_1k=Decimal("1.5000"),
        updated_at=datetime.now(timezone.utc),
    )
    dumped = read.model_dump(mode="json")
    assert dumped["input_per_1k"] == "0"
    assert dumped["output_per_1k"] == "1.5"


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_per_1k", "-0.001"),
        ("output_per_1k", "-0.001"),
        ("input_per_1k", "NaN"),
        ("output_per_1k", "Infinity"),
        ("input_per_1k", "0.00000000001"),
    ],
)
def test_create_rejects_unusable_rates(field, value):
    payload = {"provider": "openai", "model": "gpt-4o", "input_per_1k": "0.001", "output_per_1k": "0.002"}
    payload[field] = value
    with pytest.raises(ValidationError):
        LlmCostRateCreate(**payload)


@pytest.mark.parametrize("blank", ["   ", "\t", "\n"])
def test_create_rejects_whitespace_only_keys(blank):
    with pytest.raises(ValidationError):
        LlmCostRateCreate(provider=blank, model="gpt-4o", input_per_1k="0.001", output_per_1k="0.002")
    with pytest.raises(ValidationError):
        LlmCostRateCreate(provider="openai", model=blank, input_per_1k="0.001", output_per_1k="0.002")


def test_create_schema_normalizes_keys():
    dto = LlmCostRateCreate(provider="  OpenAI ", model=" GPT-4o ", input_per_1k="0.001", output_per_1k="0.002")
    assert dto.provider == "openai"
    assert dto.model == "gpt-4o"
