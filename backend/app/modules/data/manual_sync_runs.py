"""State of a knowledge base's manual sync, kept in Redis so every API process sees it."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from fastapi.encoders import jsonable_encoder

STATUS_IDLE = "idle"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"

# A sync running longer than this stops blocking a new one; it still runs to its end.
MARK_HOLD_LIMIT_SECONDS = 6 * 60 * 60
# The heartbeat renews the running mark this often.
HEARTBEAT_SECONDS = 30
# A running mark not renewed for this long lost its process.
RUNNING_TTL_SECONDS = 120
# How long the last run's result stays readable.
RESULT_TTL_SECONDS = 24 * 60 * 60

# What the page reads from a sync result; error details stay in the logs and on the KB row.
PROVIDER_RESULT_LISTS = ("zendesk_sync_results", "salesforce_sync_results")
PROVIDER_RESULT_FIELDS = ("status", "error", "message", "articles_added", "articles_updated", "articles_deleted")
PER_KB_FIELDS = ("status", "reason")

# KEYS: active key, result key. Renews the run's mark, or takes back an expired one unless the run has ended.
RENEW_OR_RETAKE = """
local holder = redis.call('GET', KEYS[1])
if holder == ARGV[1] then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
    return 1
end
if holder then
    return 0
end
local result = redis.call('GET', KEYS[2])
if result and string.find(result, ARGV[1], 1, true) then
    return 0
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""

# KEYS: active key, result key. Saves the outcome and frees the KB, unless a newer run holds it.
SAVE_RESULT_UNLESS_SUPERSEDED = """
local holder = redis.call('GET', KEYS[1])
if holder == ARGV[1] or not holder then
    redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
    redis.call('DEL', KEYS[1])
    return 1
end
return 0
"""


def _key(tenant_id: str, kb_id: str, part: str) -> str:
    # The braces put both keys of a knowledge base in one Redis Cluster slot.
    return f"kb_manual_sync:{{{tenant_id or 'master'}:{kb_id}}}:{part}"


def active_key(tenant_id: str, kb_id: str) -> str:
    return _key(tenant_id, kb_id, "active")


def result_key(tenant_id: str, kb_id: str) -> str:
    return _key(tenant_id, kb_id, "result")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick(source: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    return {name: source[name] for name in fields if name in source}


def _provider_result_for_page(result: Any) -> Any:
    if not isinstance(result, dict):
        return None
    summary = _pick(result, PROVIDER_RESULT_FIELDS)
    if "per_kb" in result:
        summary["per_kb"] = [_pick(kb, PER_KB_FIELDS) for kb in result["per_kb"] or [] if isinstance(kb, dict)]
    return summary


def result_for_page(batch_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The parts of a finished sync's result that the page shows."""
    summary: Dict[str, Any] = {"status": "completed"}
    for list_name in PROVIDER_RESULT_LISTS:
        entries = (batch_result or {}).get(list_name) or []
        summary[list_name] = [
            {"result": _provider_result_for_page(entry.get("result"))} for entry in entries if isinstance(entry, dict)
        ]
    return summary


class ManualSyncRunStore:
    """Reads and writes the manual sync state of knowledge bases."""

    def __init__(self, redis):
        self._redis = redis

    async def claim(self, tenant_id: str, kb_id: str) -> Optional[str]:
        """Mark a new run as running. Returns its id, or None while another run holds the KB."""
        run_id = str(uuid.uuid4())
        key = active_key(tenant_id, kb_id)
        claimed = await self._redis.set(key, run_id, ex=RUNNING_TTL_SECONDS, nx=True)
        # A command resent after a lost reply finds its own claim.
        holds_claim = bool(claimed) or await self._redis.get(key) == run_id
        return run_id if holds_claim else None

    async def claim_or_find_active(self, tenant_id: str, kb_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Returns (new run id, None) or (None, id of the run in progress); tried twice as a run may end in between."""
        for _ in range(2):
            run_id = await self.claim(tenant_id, kb_id)
            if run_id:
                return run_id, None
            current = await self.status(tenant_id, kb_id)
            if current["status"] == STATUS_RUNNING:
                return None, current["run_id"]
        return None, None

    async def finish(
        self,
        tenant_id: str,
        kb_id: str,
        run_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Save the run's outcome and free the KB in one step. False, with nothing written, if a newer run holds it."""
        outcome = {"status": status, "run_id": run_id, "result": result, "error": error, "finished_at": _now()}
        saved = await self._redis.eval(
            SAVE_RESULT_UNLESS_SUPERSEDED, 2, active_key(tenant_id, kb_id), result_key(tenant_id, kb_id),
            run_id, json.dumps(jsonable_encoder(outcome)), RESULT_TTL_SECONDS,
        )
        return bool(saved)

    async def status(self, tenant_id: str, kb_id: str) -> Dict[str, Any]:
        """The run in progress with the last outcome, else the last outcome, else idle."""
        active_run_id = await self._redis.get(active_key(tenant_id, kb_id))
        stored_outcome = await self._redis.get(result_key(tenant_id, kb_id))
        last_outcome = json.loads(stored_outcome) if stored_outcome else None
        if active_run_id:
            return {"status": STATUS_RUNNING, "run_id": active_run_id, "previous": last_outcome}
        return last_outcome or {"status": STATUS_IDLE}
