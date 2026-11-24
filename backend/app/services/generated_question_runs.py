"""State of a dataset's question-writing run, kept in Redis so the API and the workers see the same."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

STATUS_IDLE = "idle"
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_STOPPED = "stopped"
STATUS_FAILED = "failed"
IN_PROGRESS = (STATUS_QUEUED, STATUS_RUNNING)

# A run waits for the worker behind other long jobs; it holds the dataset this long before it starts.
QUEUED_TTL_SECONDS = 6 * 60 * 60
# Once started, a run that has not reported for this long lost its worker.
RUNNING_TTL_SECONDS = 30 * 60
# How long the last run's outcome stays readable.
RESULT_TTL_SECONDS = 24 * 60 * 60
COUNTS = ("articles_total", "articles_done", "articles_failed", "messages_added", "messages_dropped")
NOT_STARTED_ERROR = "The run did not start. Try again."
RUN_LOST_ERROR = "The run stopped before it finished."


def _key(tenant_id: str, suite_id: str, part: str) -> str:
    return f"generated_questions:{tenant_id}:{suite_id}:{part}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GeneratedQuestionRunStore:
    """Reads and writes the question-writing state of datasets."""

    def __init__(self, redis):
        self._redis = redis

    async def claim(self, tenant_id: str, suite_id: str, knowledge_base_id: str) -> Optional[str]:
        """Mark a new run as queued and return its id; None while another run holds this dataset."""
        run_id = str(uuid.uuid4())
        claimed = await self._redis.set(_key(tenant_id, suite_id, "active"), run_id, ex=QUEUED_TTL_SECONDS, nx=True)
        if not claimed:
            return None
        state = {"status": STATUS_QUEUED, "run_id": run_id, "knowledge_base_id": knowledge_base_id,
                 "started_at": _now(), **dict.fromkeys(COUNTS, 0)}
        await self._write(tenant_id, suite_id, state)
        return run_id

    async def report(self, tenant_id: str, suite_id: str, run_id: str, counts: Dict[str, int]) -> bool:
        """Mark the run as running with its counts so far. False when it no longer holds the dataset."""
        key = _key(tenant_id, suite_id, "active")
        if await self._redis.get(key) != run_id:
            return False
        await self._redis.expire(key, RUNNING_TTL_SECONDS)
        state = await self._read(tenant_id, suite_id) or {"run_id": run_id}
        state.update({**counts, "status": STATUS_RUNNING})
        await self._write(tenant_id, suite_id, state)
        return True

    async def holds(self, tenant_id: str, suite_id: str, run_id: str) -> bool:
        """Whether the run still holds the dataset."""
        return await self._redis.get(_key(tenant_id, suite_id, "active")) == run_id

    async def finish(
        self,
        tenant_id: str,
        suite_id: str,
        run_id: str,
        status: str,
        error: Optional[str] = None,
        counts: Optional[Dict[str, int]] = None,
    ) -> None:
        """Save the run's outcome and free the dataset; a newer run's state and mark are left alone."""
        state = await self._read(tenant_id, suite_id)
        if not state or state.get("run_id") != run_id:
            return
        state.update({**(counts or {}), "status": status, "error": error, "finished_at": _now()})
        await self._write(tenant_id, suite_id, state)
        key = _key(tenant_id, suite_id, "active")
        if await self._redis.get(key) == run_id:
            await self._redis.delete(key)

    async def status(self, tenant_id: str, suite_id: str) -> Dict[str, Any]:
        """The run in progress, else the last run's outcome, else idle."""
        state = await self._read(tenant_id, suite_id)
        if not state:
            return {"status": STATUS_IDLE}
        if state.get("status") not in IN_PROGRESS:
            return state
        holder = await self._redis.get(_key(tenant_id, suite_id, "active"))
        if holder == state.get("run_id"):
            return state
        never_started = state.get("status") == STATUS_QUEUED
        return {**state, "status": STATUS_FAILED, "error": NOT_STARTED_ERROR if never_started else RUN_LOST_ERROR}

    async def _read(self, tenant_id: str, suite_id: str) -> Optional[Dict[str, Any]]:
        stored = await self._redis.get(_key(tenant_id, suite_id, "state"))
        return json.loads(stored) if stored else None

    async def _write(self, tenant_id: str, suite_id: str, state: Dict[str, Any]) -> None:
        await self._redis.set(_key(tenant_id, suite_id, "state"), json.dumps(state), ex=RESULT_TTL_SECONDS)
