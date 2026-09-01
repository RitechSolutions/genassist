import csv
import io
import logging
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
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
from app.services.llm_pricing_cache import (
    invalidate_llm_cost_rates_cache,
    invalidate_llm_cost_rates_cache_after_commit,
)

logger = logging.getLogger(__name__)

# Cache rate columns stay optional so files written for the 4-column format still import
_REQUIRED_COLUMNS = frozenset({"provider", "model", "input_per_1k", "output_per_1k"})
_BASE_COLUMNS = ["provider", "model", "input_per_1k", "output_per_1k"]
_CACHE_COLUMNS = ["cache_read_per_1k", "cache_creation_per_1k"]

MAX_IMPORT_BYTES = 1 * 1024 * 1024
MAX_IMPORT_ROWS = 10_000
MAX_IMPORT_ERRORS = 100


def import_exceeds_byte_cap(raw: bytes) -> bool:
    return len(raw) > MAX_IMPORT_BYTES


def _capped_errors(errors: list[str]) -> list[str]:
    if len(errors) <= MAX_IMPORT_ERRORS:
        return errors
    omitted = len(errors) - MAX_IMPORT_ERRORS
    return [*errors[:MAX_IMPORT_ERRORS], f"… {omitted} additional errors omitted"]


def _rate_key(provider_key: str | None, model_key: str | None) -> tuple[str, str]:
    return (provider_key or "").strip().lower(), (model_key or "").strip().lower()


def _optional_rate(value: Decimal | None) -> str:
    return "" if value is None else format_rate(value)


def _parse_header(fieldnames: Sequence[str] | None) -> tuple[dict[str, str], set[str], str | None]:
    """Original-case column lookup and normalized names, or why the header is unusable"""
    if not fieldnames:
        return {}, set(), "CSV has no header row"

    names = [(h or "").strip().lower() for h in fieldnames]
    counts = Counter(name for name in names if name)
    if any(count > 1 for count in counts.values()):
        duplicates = sorted(h for h, count in counts.items() if count > 1)
        return {}, set(), f"Duplicate columns: {', '.join(duplicates)}"

    headers = set(counts)
    if not _REQUIRED_COLUMNS.issubset(headers):
        missing = _REQUIRED_COLUMNS - headers
        return {}, set(), f"Missing columns: {', '.join(sorted(missing))}"

    original_header: dict[str, str] = {}
    for name, raw in zip(names, fieldnames):
        if name:
            original_header.setdefault(name, raw)
    return original_header, headers, None


def _parse_rows(
    reader: csv.DictReader, original_header: dict[str, str]
) -> tuple[list[LlmCostRateCreate], list[str], str | None]:
    """Accepted rows plus per-row errors, or why the whole file is rejected"""

    def col(row: dict[str, str], name: str) -> str:
        key = original_header.get(name)
        return "" if key is None else (row.get(key) or "").strip()

    errors: list[str] = []
    seen_keys: dict[tuple[str, str], int] = {}
    parsed: list[LlmCostRateCreate] = []
    for i, row in enumerate(reader, start=2):
        if i - 1 > MAX_IMPORT_ROWS:
            return [], [], f"CSV has more than {MAX_IMPORT_ROWS} data rows"
        # Every row goes through the create schema, so CSV and JSON reject
        # blank keys, negatives, non-finite and over-precise rates alike
        try:
            dto = LlmCostRateCreate(
                provider=col(row, "provider"),
                model=col(row, "model"),
                input_per_1k=col(row, "input_per_1k"),
                output_per_1k=col(row, "output_per_1k"),
                cache_read_per_1k=col(row, "cache_read_per_1k"),
                cache_creation_per_1k=col(row, "cache_creation_per_1k"),
            )
        except ValidationError:
            errors.append(f"Row {i}: invalid provider, model or rate value")
            continue

        key = (dto.provider, dto.model)
        if key in seen_keys:
            errors.append(f"Row {i}: duplicate of row {seen_keys[key]} for {dto.provider}/{dto.model}")
            continue
        seen_keys[key] = i
        parsed.append(dto)
    return parsed, errors, None


@inject
class LlmCostRateService:
    def __init__(self, repo: LlmCostRateRepository):
        self.repo = repo

    async def list_active(self) -> list[LlmCostRateModel]:
        return await self.repo.list_active()

    async def export_csv(self, include_cache_rates: bool) -> str:
        """
        Export the current rates in a format the importer accepts. Unconfigured cache rates export blank, so a
        round-trip keeps them unset.
        """
        rows = await self.repo.list_active()
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow((_BASE_COLUMNS + _CACHE_COLUMNS) if include_cache_rates else _BASE_COLUMNS)
        for r in rows:
            values = [
                (r.provider_key or "").strip(),
                (r.model_key or "").strip(),
                format_rate(r.input_per_1k),
                format_rate(r.output_per_1k),
            ]
            if include_cache_rates:
                values += [_optional_rate(r.cache_read_per_1k), _optional_rate(r.cache_creation_per_1k)]
            writer.writerow(values)
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
                cache_read_per_1k=dto.cache_read_per_1k,
                cache_creation_per_1k=dto.cache_creation_per_1k,
                updated_at=datetime.now(timezone.utc),
            )
        )
        invalidate_llm_cost_rates_cache_after_commit(self.repo.db, tenant)
        return LlmCostRateRead.model_validate(created, from_attributes=True)

    async def update_rate(self, rate_id: UUID, dto: LlmCostRateUpdate) -> LlmCostRateRead | None:
        """Edit an active rate's prices. Returns None when the rate is missing"""
        tenant = get_tenant_context()
        row = await self.repo.get_active_by_id(rate_id)
        if not row:
            return None
        row.input_per_1k = dto.input_per_1k
        row.output_per_1k = dto.output_per_1k
        if "cache_read_per_1k" in dto.model_fields_set:
            row.cache_read_per_1k = dto.cache_read_per_1k
        if "cache_creation_per_1k" in dto.model_fields_set:
            row.cache_creation_per_1k = dto.cache_creation_per_1k
        row.updated_at = datetime.now(timezone.utc)
        updated = await self.repo.update(row)
        invalidate_llm_cost_rates_cache_after_commit(self.repo.db, tenant)
        return LlmCostRateRead.model_validate(updated, from_attributes=True)

    async def delete_by_id(self, rate_id: UUID) -> bool:
        tenant = get_tenant_context()
        ok = await self.repo.soft_delete_by_id(rate_id)
        if ok:
            invalidate_llm_cost_rates_cache_after_commit(self.repo.db, tenant)
        return ok

    async def _apply_rows(self, parsed: list[LlmCostRateCreate], headers: set[str]) -> tuple[int, int]:
        """Stage inserts and updates. Cache columns absent from the header keep their stored value"""
        index = {_rate_key(r.provider_key, r.model_key): r for r in await self.repo.list_active()}
        inserted = 0
        updated = 0

        for dto in parsed:
            existing = index.get((dto.provider, dto.model))
            if existing:
                existing.input_per_1k = dto.input_per_1k
                existing.output_per_1k = dto.output_per_1k
                if "cache_read_per_1k" in headers:
                    existing.cache_read_per_1k = dto.cache_read_per_1k
                if "cache_creation_per_1k" in headers:
                    existing.cache_creation_per_1k = dto.cache_creation_per_1k
                # Defensive: older schema/model mismatch could leave this NULL.
                existing.updated_at = datetime.now(timezone.utc)
                self.repo.db.add(existing)
                updated += 1
            else:
                created = LlmCostRateModel(
                    provider_key=dto.provider,
                    model_key=dto.model,
                    input_per_1k=dto.input_per_1k,
                    output_per_1k=dto.output_per_1k,
                    cache_read_per_1k=dto.cache_read_per_1k,
                    cache_creation_per_1k=dto.cache_creation_per_1k,
                    updated_at=datetime.now(timezone.utc),
                )
                self.repo.db.add(created)
                index[(dto.provider, dto.model)] = created
                inserted += 1

        return inserted, updated

    async def import_csv(self, text: str) -> LlmCostRateImportResult:
        tenant = get_tenant_context()
        reader = csv.DictReader(io.StringIO(text))

        original_header, headers, header_error = _parse_header(reader.fieldnames)
        if header_error:
            return LlmCostRateImportResult(inserted=0, updated=0, errors=[header_error])

        parsed, errors, file_error = _parse_rows(reader, original_header)
        if file_error:
            return LlmCostRateImportResult(inserted=0, updated=0, errors=[file_error])

        inserted, updated = await self._apply_rows(parsed, headers)
        errors = _capped_errors(errors)

        try:
            await self.repo.db.commit()
        except IntegrityError:
            await self.repo.db.rollback()
            logger.warning("LLM cost rate import rejected by the database", exc_info=True)
            errors.append("No rows were imported: the file conflicts with existing rates")
            return LlmCostRateImportResult(inserted=0, updated=0, errors=errors)

        if inserted or updated:
            invalidate_llm_cost_rates_cache(tenant)
        return LlmCostRateImportResult(inserted=inserted, updated=updated, errors=errors)
