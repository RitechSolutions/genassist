import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from injector import inject

from app.core.config.llm_pricing import PricingStatus
from app.repositories.llm_usage_backfill import LlmUsageBackfillRepository
from app.repositories.llm_usage_control import LlmUsageControlRepository

logger = logging.getLogger(__name__)

BACKFILL_PAGE_SIZE = 1000

LEGACY_SOURCE = "chat"
LEGACY_SOURCE_TYPE = "workflow"

_USAGE_FIELDS = ("input_tokens", "output_tokens", "total_tokens", "cost_usd")

# Copied cost comes from a Float column, so parity allows ±max($0.01, 0.05%)
COST_ABS_TOLERANCE_USD = Decimal("0.01")
COST_REL_TOLERANCE = Decimal("0.0005")


@dataclass
class ResolvedUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Optional[Decimal]
    pricing_status: str


def _payload_usage(raw_response: Any) -> dict[str, Any]:
    """Pull token_usage + cost_usd out of a stored raw_response payload; {} on bad data"""
    if not raw_response:
        return {}
    try:
        payload = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    token_usage = payload.get("token_usage")
    token_usage = token_usage if isinstance(token_usage, dict) else {}
    return {
        "input_tokens": token_usage.get("input_tokens"),
        "output_tokens": token_usage.get("output_tokens"),
        "total_tokens": token_usage.get("total_tokens"),
        "cost_usd": payload.get("cost_usd"),
    }


def _as_number(value: Any) -> Optional[float]:
    """Numeric value or None. Drops non-numeric payload junk (strings, lists, bools)
    so one bad raw_response can't abort a page — mirrors llm_usage_utils._first_present"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def resolve_backfill_usage(typed: dict[str, Any], payload: dict[str, Any]) -> Optional[ResolvedUsage]:
    """Merge a log's typed columns with its payload fallback and classify it"""
    merged = {
        field: _as_number(typed[field] if typed.get(field) is not None else payload.get(field))
        for field in _USAGE_FIELDS
    }
    if all(merged[field] is None for field in _USAGE_FIELDS):
        return None

    # Clamp so corrupt legacy values can't violate the non-negative / total_ge_parts
    # CHECKs and abort a whole page
    input_tokens = max(0, int(merged["input_tokens"])) if merged["input_tokens"] is not None else 0
    output_tokens = max(0, int(merged["output_tokens"])) if merged["output_tokens"] is not None else 0
    total_tokens = int(merged["total_tokens"]) if merged["total_tokens"] is not None else input_tokens + output_tokens
    total_tokens = max(total_tokens, input_tokens + output_tokens)

    cost = merged["cost_usd"]
    if cost is not None:
        return ResolvedUsage(
            input_tokens, output_tokens, total_tokens, Decimal(str(cost)), PricingStatus.LEGACY_ESTIMATE.value
        )
    return ResolvedUsage(input_tokens, output_tokens, total_tokens, None, PricingStatus.UNPRICED.value)


def _check_parity(
    eligible: int,
    input_sum: int,
    output_sum: int,
    total_sum: int,
    cost_sum: Decimal,
    ledger_count: int,
    ledger_in: int,
    ledger_out: int,
    ledger_total: int,
    ledger_cost: Decimal,
) -> dict[str, Any]:
    counts_match = eligible == ledger_count
    tokens_match = (input_sum, output_sum, total_sum) == (ledger_in, ledger_out, ledger_total)
    cost_delta = abs(cost_sum - ledger_cost)
    cost_tolerance = max(COST_ABS_TOLERANCE_USD, abs(cost_sum) * COST_REL_TOLERANCE)
    cost_within_tolerance = cost_delta <= cost_tolerance
    return {
        "ok": counts_match and tokens_match and cost_within_tolerance,
        "counts_match": counts_match,
        "tokens_match": tokens_match,
        "cost_within_tolerance": cost_within_tolerance,
        "eligible": eligible,
        "ledger_count": ledger_count,
        "cost_delta_usd": str(cost_delta),
        "cost_tolerance_usd": str(cost_tolerance),
    }


@inject
class LlmUsageBackfillService:
    """Fills the ledger with aggregate events for chat history that predates capture activation"""

    def __init__(self, repo: LlmUsageBackfillRepository, control_repo: LlmUsageControlRepository):
        self.repo = repo
        self.control_repo = control_repo

    async def run(self, force: bool = False) -> dict[str, Any]:
        control = await self.control_repo.get_singleton()
        boundary = control.capture_started_at if control else None
        if boundary is None:
            logger.info("LLM usage backfill skipped: capture not activated")
            return {"status": "skipped", "reason": "capture_not_activated"}

        logs_seen = 0
        no_usage_skipped = 0
        events_written = 0
        input_sum = 0
        output_sum = 0
        total_sum = 0
        cost_sum = Decimal(0)
        legacy_estimate_count = 0
        unpriced_count = 0
        after_id = None

        while True:
            page = await self.repo.fetch_log_page(boundary, after_id, BACKFILL_PAGE_SIZE)
            if not page:
                break
            after_id = page[-1].id

            null_ids = [row.id for row in page if any(getattr(row, f) is None for f in _USAGE_FIELDS)]
            raw_by_id = await self.repo.fetch_raw_responses(null_ids)
            conversation_ids = {row.conversation_id for row in page}
            valid_conversations = await self.repo.existing_conversation_ids(conversation_ids)
            agent_by_conversation = await self.repo.resolve_agent_workflow(conversation_ids)

            event_rows = []
            for row in page:
                logs_seen += 1
                typed = {f: getattr(row, f) for f in _USAGE_FIELDS}
                payload = _payload_usage(raw_by_id.get(row.id))
                resolved = resolve_backfill_usage(typed, payload)
                if resolved is None:
                    no_usage_skipped += 1
                    continue

                agent_id, workflow_id = agent_by_conversation.get(row.conversation_id, (None, None))

                input_sum += resolved.input_tokens
                output_sum += resolved.output_tokens
                total_sum += resolved.total_tokens
                if resolved.cost_usd is not None:
                    cost_sum += resolved.cost_usd
                    legacy_estimate_count += 1
                else:
                    unpriced_count += 1

                event_rows.append(
                    {
                        "execution_id": f"legacy:{row.id}",
                        "call_index": 0,
                        "source_type": LEGACY_SOURCE_TYPE,
                        "source": LEGACY_SOURCE,
                        "agent_id": agent_id,
                        "workflow_id": workflow_id,
                        "conversation_id": row.conversation_id if row.conversation_id in valid_conversations else None,
                        "legacy_response_log_id": row.id,
                        "input_tokens": resolved.input_tokens,
                        "prompt_tokens": resolved.input_tokens,
                        "output_tokens": resolved.output_tokens,
                        "total_tokens": resolved.total_tokens,
                        "cost_usd": resolved.cost_usd,
                        "pricing_status": resolved.pricing_status,
                        "occurred_at": row.logged_at,
                    }
                )

            events_written += await self.repo.insert_events(event_rows, force)

        eligible = logs_seen - no_usage_skipped
        ledger_count, ledger_in, ledger_out, ledger_total, ledger_cost = await self.repo.legacy_event_aggregates()
        parity = _check_parity(
            eligible,
            input_sum,
            output_sum,
            total_sum,
            cost_sum,
            ledger_count,
            ledger_in,
            ledger_out,
            ledger_total,
            ledger_cost,
        )

        summary = {
            "status": "completed",
            "force": force,
            "boundary": boundary.isoformat(),
            "logs_seen": logs_seen,
            "no_usage_skipped": no_usage_skipped,
            "eligible": eligible,
            "events_written": events_written,
            "legacy_events_total": ledger_count,
            "input_tokens": input_sum,
            "output_tokens": output_sum,
            "total_tokens": total_sum,
            "copied_cost_usd": str(cost_sum),
            "legacy_estimate_count": legacy_estimate_count,
            "unpriced_count": unpriced_count,
            "parity": parity,
        }
        if not parity["ok"]:
            logger.warning("LLM usage backfill parity mismatch: %s", parity)
        logger.info("LLM usage backfill complete: %s", summary)
        return summary
