"""
Background jobs for workflow test runs that train a model.

Testing a workflow or a single node that contains a Train Model node used to
run the training inside the API request. A large hyperparameter search then
held the API process (and every other page) for minutes or took it down.
Such test runs now become a job on the "ml" Celery worker: the endpoint
returns a job id straight away and the UI polls the job's status.

Job state lives in Redis, scoped to the tenant and the user who started it,
and expires after ML_TRAINING_JOB_TTL_SECONDS. A user has at most one queued
or running job; the endpoint hands back that job instead of starting a second,
and the user can cancel it.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi.encoders import jsonable_encoder

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

TRAIN_MODEL_NODE_TYPE = "trainModelNode"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
FINISHED_STATUSES = (STATUS_SUCCEEDED, STATUS_FAILED, STATUS_CANCELLED)
CANCELLED_ERROR = "The training test was cancelled."

# The worker writes a heartbeat this often while a job runs. A running job
# with no heartbeat for STALE_AFTER_SECONDS lost its worker (restart, crash).
HEARTBEAT_SECONDS = 5
STALE_AFTER_SECONDS = 120
WORKER_LOST_ERROR = "The training worker stopped while running this job. Run the test again."

# Matches the timeout run_training_job_task passes to run_async_in_celery.
JOB_TIMEOUT_SECONDS = 2 * 60 * 60
# A job no worker has started by then is given up: no "ml" worker is running,
# or the queue is too long. Jobs started later than this skip themselves.
QUEUED_TIMEOUT_SECONDS = JOB_TIMEOUT_SECONDS + 10 * 60
NOT_STARTED_ERROR = "No training worker started this job in time. Run the test again later."


def _node_field(node: Any, name: str) -> Any:
    return node.get(name) if isinstance(node, dict) else getattr(node, name, None)


def train_model_nodes(nodes: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
    """The Train Model nodes' data (configuration) in a workflow's node list."""
    found = []
    for node in nodes or []:
        if _node_field(node, "type") == TRAIN_MODEL_NODE_TYPE:
            data = _node_field(node, "data")
            found.append(data if isinstance(data, dict) else {})
    return found


def check_training_config(node_data: Dict[str, Any]) -> None:
    """Refuse a Train Model node whose hyperparameter search is too large."""
    from app.modules.workflow.engine.nodes.ml import hyperparameter_optimization as hpo_module

    model_type = node_data.get("modelType")
    model_parameters = node_data.get("modelParameters") or {}
    optimization_config = node_data.get("optimizationConfig") or {}
    # Templated values ({{...}}) are only known at run time; the node checks
    # again once they are resolved.
    if not isinstance(model_type, str) or not isinstance(model_parameters, dict) or not isinstance(
        optimization_config, dict
    ):
        return
    try:
        hpo_module.check_search_size(
            model_type.lower(),
            model_parameters,
            node_data.get("hyperparameterOptimization") or "none",
            optimization_config,
        )
    except (TypeError, ValueError):
        # A malformed option (e.g. "cvFolds": "three") is reported by the node itself.
        return


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_key(tenant_id: str, job_id: str) -> str:
    return f"ml_training_job:{tenant_id or 'master'}:{job_id}"


def heartbeat_key(tenant_id: str, job_id: str) -> str:
    """Written by the worker's heartbeat thread with the job's latest progress.

    A separate key, so the thread never rewrites the job itself and can't
    overwrite a status the job's own updates wrote.
    """
    return f"ml_training_job_heartbeat:{tenant_id or 'master'}:{job_id}"


def heartbeat_value(progress: Dict[str, Any]) -> str:
    return json.dumps({"at": time.time(), "progress": jsonable_encoder(progress)})


def _active_key(tenant_id: str, user_id: str) -> str:
    return f"ml_training_job_active:{tenant_id or 'master'}:{user_id}"


# Replace the user's active job id only if it is still the one we read, so
# two requests that both found a finished job can't both take its place.
_REPLACE_IF_UNCHANGED = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
end
return false
"""
_CLAIM_ATTEMPTS = 3


class TrainingJobStore:
    """Reads and writes training job state in Redis."""

    def __init__(self, redis):
        self._redis = redis

    async def start(
        self, tenant_id: str, user_id: str, kind: str
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Create a queued job for the user, unless they already have one.

        Returns (new job, None), or (None, the user's queued or running job).
        Claiming the user's slot is atomic, so a double-click queues one job.
        """
        if not user_id:
            raise ValueError("A training job needs an owner")
        job_id = str(uuid.uuid4())
        key = _active_key(tenant_id, user_id)
        for _ in range(_CLAIM_ATTEMPTS):
            if await self._redis.set(key, job_id, ex=QUEUED_TIMEOUT_SECONDS, nx=True):
                return await self._create(tenant_id, user_id, kind, job_id), None
            current_id = await self._redis.get(key)
            if current_id is None:
                continue  # expired between the two calls
            current = await self.get(tenant_id, current_id)
            if current is not None and public_view(current)["status"] not in FINISHED_STATUSES:
                return None, current
            if await self._redis.eval(_REPLACE_IF_UNCHANGED, 1, key, current_id, job_id, QUEUED_TIMEOUT_SECONDS):
                return await self._create(tenant_id, user_id, kind, job_id), None
        # Other requests kept taking the slot: report whichever job holds it now.
        current_id = await self._redis.get(key)
        current = await self.get(tenant_id, current_id) if current_id else None
        if current is None:
            raise RuntimeError("Could not claim a training job slot")
        return None, current

    async def _create(self, tenant_id: str, user_id: str, kind: str, job_id: str) -> Dict[str, Any]:
        job = {
            "job_id": job_id,
            "kind": kind,
            "status": STATUS_QUEUED,
            "progress": {"stage": "queued", "message": "Waiting for a training worker", "percent": 0},
            "user_id": user_id,
            "created_at": _now(),
            "updated_at": _now(),
            "heartbeat": time.time(),
            "result": None,
            "error": None,
        }
        await self._save(tenant_id, job)
        return job

    async def active_job(self, tenant_id: str, user_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """The user's queued or running job, if they have one."""
        if not user_id:
            return None
        job_id = await self._redis.get(_active_key(tenant_id, user_id))
        job = await self.get(tenant_id, job_id) if job_id else None
        if job is None or public_view(job)["status"] in FINISHED_STATUSES:
            return None
        return job

    async def get(self, tenant_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        raw = await self._redis.get(job_key(tenant_id, job_id))
        if not raw:
            return None
        job = json.loads(raw)
        if job.get("status") == STATUS_RUNNING:
            beat = await self._redis.get(heartbeat_key(tenant_id, job_id))
            if beat:
                beat = json.loads(beat)
                if beat["at"] > float(job.get("heartbeat") or 0):
                    job["heartbeat"] = beat["at"]
                    job["progress"] = beat["progress"]
        return job

    async def cancel(self, tenant_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        """Mark a queued or running job cancelled; a finished job is returned as it is.

        A queued job then skips itself when a worker picks it up; the worker
        running a job sees the status on its next heartbeat and stops.
        """
        job = await self.get(tenant_id, job_id)
        if job is None or public_view(job)["status"] in FINISHED_STATUSES:
            return job
        return await self.update(tenant_id, job_id, status=STATUS_CANCELLED, error=CANCELLED_ERROR)

    async def update(self, tenant_id: str, job_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        job = await self.get(tenant_id, job_id)
        if job is None:
            return None
        job.update(fields)
        job["updated_at"] = _now()
        job["heartbeat"] = time.time()
        await self._save(tenant_id, job)
        return job

    async def _save(self, tenant_id: str, job: Dict[str, Any]) -> None:
        await self._redis.set(
            job_key(tenant_id, job["job_id"]),
            json.dumps(jsonable_encoder(job)),
            ex=settings.ML_TRAINING_JOB_TTL_SECONDS,
        )


def public_view(job: Dict[str, Any]) -> Dict[str, Any]:
    """The job as returned by the API: a lost worker, or a job no worker
    started in time, shows as a failed job."""
    view = {key: value for key, value in job.items() if key not in ("user_id", "heartbeat")}
    # Queued jobs are never updated, so their heartbeat is when they were created.
    silent_for = time.time() - float(job.get("heartbeat") or 0)
    if job.get("status") == STATUS_RUNNING and silent_for > STALE_AFTER_SECONDS:
        view["status"] = STATUS_FAILED
        view["error"] = WORKER_LOST_ERROR
    elif job.get("status") == STATUS_QUEUED and silent_for > QUEUED_TIMEOUT_SECONDS:
        view["status"] = STATUS_FAILED
        view["error"] = NOT_STARTED_ERROR
    return view
