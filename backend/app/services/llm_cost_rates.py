import csv
import io
import logging
from datetime import datetime, timezone
from uuid import UUID

from injector import inject
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import get_tenant_context
from app.db.models.llm_cost_rate import LlmCostRateModel
from app.repositories.llm_cost_rates import LlmCostRateRepository
from app.schemas.llm_cost_rate import (
    LlmCostRateCreate,
    LlmCostRateImportResult,
    LlmCostRateRead,
    LlmCostRateUpdate,
    format_rate,
)
from app.services.llm_pricing_cache import invalidate_llm_cost_rates_cache

logger = logging.getLogger(__name__)

_REQUIRED_COLUMNS = frozenset({"provider", "model", "input_per_1k", "output_per_1k"})


@inject
class LlmCostRateService:
    def __init__(self, repo: LlmCostRateRepository):
        self.repo = repo

    async def list_active(self) -> list[LlmCostRateModel]:
        return await self.repo.list_active()

    async def export_csv(self) -> str:
        """
        Export the current rates in the same 4-column format the importer accepts.
        """
        rows = await self.repo.list_active()
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["provider", "model", "input_per_1k", "output_per_1k"])
        for r in rows:
            writer.writerow(
                [
                    (r.provider_key or "").strip(),
                    (r.model_key or "").strip(),
                    format_rate(r.input_per_1k),
                    format_rate(r.output_per_1k),
                ]
            )
        return out.getvalue()

    async def create_rate(self, dto: LlmCostRateCreate) -> LlmCostRateRead:
        """Insert one rate. 409 if an active rate for the same provider+model exists"""
        tenant = get_tenant_context()
        provider = dto.provider
        model = dto.model
        existing = await self.repo.get_active_by_provider_model(provider, model)
        if existing:
            raise AppException(error_key=ErrorKey.LLM_COST_RATE_ALREADY_EXISTS, status_code=409)
        created = await self.repo.create(
            LlmCostRateModel(
                provider_key=provider,
                model_key=model,
                input_per_1k=dto.input_per_1k,
                output_per_1k=dto.output_per_1k,
                updated_at=datetime.now(timezone.utc),
            )
        )
        invalidate_llm_cost_rates_cache(tenant)
        return LlmCostRateRead.model_validate(created, from_attributes=True)

    async def update_rate(self, rate_id: UUID, dto: LlmCostRateUpdate) -> LlmCostRateRead | None:
        """Edit an active rate's prices. Returns None when the rate is missing"""
        tenant = get_tenant_context()
        row = await self.repo.get_active_by_id(rate_id)
        if not row:
            return None
        row.input_per_1k = dto.input_per_1k
        row.output_per_1k = dto.output_per_1k
        row.updated_at = datetime.now(timezone.utc)
        updated = await self.repo.update(row)
        invalidate_llm_cost_rates_cache(tenant)
        return LlmCostRateRead.model_validate(updated, from_attributes=True)

    async def delete_by_id(self, rate_id: UUID) -> bool:
        tenant = get_tenant_context()
        ok = await self.repo.soft_delete_by_id(rate_id)
        if ok:
            invalidate_llm_cost_rates_cache(tenant)
        return ok

    async def import_csv(self, text: str) -> LlmCostRateImportResult:
        tenant = get_tenant_context()
        inserted = 0
        updated = 0
        errors: list[str] = []

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return LlmCostRateImportResult(
                inserted=0, updated=0, errors=["CSV has no header row"]
            )
        headers = {h.strip().lower() for h in reader.fieldnames if h}
        if not _REQUIRED_COLUMNS.issubset(headers):
            missing = _REQUIRED_COLUMNS - headers
            return LlmCostRateImportResult(
                inserted=0,
                updated=0,
                errors=[f"Missing columns: {', '.join(sorted(missing))}"],
            )

        def col(row: dict[str, str], name: str) -> str:
            for k, v in row.items():
                if k and k.strip().lower() == name:
                    return (v or "").strip()
            return ""

        seen_keys: dict[tuple[str, str], int] = {}
        for i, row in enumerate(reader, start=2):
            # Every row goes through the create schema, so CSV and JSON reject
            # blank keys, negatives, non-finite and over-precise rates alike
            try:
                dto = LlmCostRateCreate(
                    provider=col(row, "provider"),
                    model=col(row, "model"),
                    input_per_1k=col(row, "input_per_1k"),
                    output_per_1k=col(row, "output_per_1k"),
                )
            except ValidationError:
                errors.append(f"Row {i}: invalid provider, model, input_per_1k or output_per_1k")
                continue

            key = (dto.provider, dto.model)
            if key in seen_keys:
                errors.append(f"Row {i}: duplicate of row {seen_keys[key]} for {dto.provider}/{dto.model}")
                continue
            seen_keys[key] = i

            existing = await self.repo.get_active_by_provider_model(dto.provider, dto.model)
            if existing:
                existing.input_per_1k = dto.input_per_1k
                existing.output_per_1k = dto.output_per_1k
                # Defensive: older schema/model mismatch could leave this NULL.
                existing.updated_at = datetime.now(timezone.utc)
                self.repo.db.add(existing)
                updated += 1
            else:
                self.repo.db.add(
                    LlmCostRateModel(
                        provider_key=dto.provider,
                        model_key=dto.model,
                        input_per_1k=dto.input_per_1k,
                        output_per_1k=dto.output_per_1k,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                inserted += 1

        try:
            await self.repo.db.commit()
        except IntegrityError:
            await self.repo.db.rollback()
            logger.warning("LLM cost rate import rejected by the database", exc_info=True)
            errors.append("No rows were imported: the file conflicts with existing rates")
            return LlmCostRateImportResult(inserted=0, updated=0, errors=errors)

        invalidate_llm_cost_rates_cache(tenant)
        return LlmCostRateImportResult(inserted=inserted, updated=updated, errors=errors)
