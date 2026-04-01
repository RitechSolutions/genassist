import csv
import io
import logging
from decimal import Decimal, InvalidOperation
from uuid import UUID

from injector import inject

from app.core.tenant_scope import get_tenant_context
from app.db.models.llm_cost_rate import LlmCostRateModel
from app.repositories.llm_cost_rates import LlmCostRateRepository
from app.schemas.llm_cost_rate import LlmCostRateImportResult
from app.services.llm_pricing_cache import invalidate_llm_cost_rates_cache

logger = logging.getLogger(__name__)

_REQUIRED_COLUMNS = frozenset({"provider", "model", "input_per_1k", "output_per_1k"})


@inject
class LlmCostRateService:
    def __init__(self, repo: LlmCostRateRepository):
        self.repo = repo

    async def list_active(self) -> list[LlmCostRateModel]:
        return await self.repo.list_active()

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

        for i, row in enumerate(reader, start=2):
            prov = col(row, "provider").lower()
            mod = col(row, "model").lower()
            if not prov or not mod:
                errors.append(f"Row {i}: provider and model are required")
                continue
            inp_s = col(row, "input_per_1k")
            out_s = col(row, "output_per_1k")
            try:
                inp = float(Decimal(inp_s))
                out = float(Decimal(out_s))
            except (InvalidOperation, ValueError):
                errors.append(f"Row {i}: invalid input_per_1k or output_per_1k")
                continue

            existing = await self.repo.get_active_by_provider_model(prov, mod)
            if existing:
                existing.input_per_1k = inp
                existing.output_per_1k = out
                self.repo.db.add(existing)
                updated += 1
            else:
                self.repo.db.add(
                    LlmCostRateModel(
                        provider_key=prov,
                        model_key=mod,
                        input_per_1k=inp,
                        output_per_1k=out,
                    )
                )
                inserted += 1

        await self.repo.db.commit()
        invalidate_llm_cost_rates_cache(tenant)
        return LlmCostRateImportResult(inserted=inserted, updated=updated, errors=errors)
