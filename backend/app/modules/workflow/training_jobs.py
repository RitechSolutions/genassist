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
# The user's slot lives as long as a job can: the longest wait for a worker
# plus the longest run. A job that finishes sooner frees it by its status.
ACTIVE_SLOT_TTL_SECONDS = QUEUED_TIMEOUT_SECONDS + JOB_TIMEOUT_SECONDS + STALE_AFTER_SECONDS


def _node_field(node: Any, name: str) -> Any:
    return node.get(name) if isinstance(node, dict) else getattr(node, name, None)


# Edges into these handles attach a node (a tool, a sub-agent) to the node they
# point at; the attached node runs as part of it.
_ATTACHMENT_HANDLES = frozenset({"input_tools", "input_sub_agents"})


def _reachable_node_ids(
    nodes: List[Any], edges: Iterable[Dict[str, Any]], start_node_id: Optional[str]
) -> set:
    """Ids of the nodes a turn can run: those reachable from where it starts.

    A turn starts at start_node_id (a resume), else at every node with no
    incoming edge. From each node it can go on along its outgoing edges, and
    it can run the nodes attached to it as tools or sub-agents.
    """
    outgoing: Dict[str, List[str]] = {}
    attached: Dict[str, List[str]] = {}
    has_incoming = set()
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if not source or not target:
            continue
        outgoing.setdefault(source, []).append(target)
        has_incoming.add(target)
        if edge.get("targetHandle") in _ATTACHMENT_HANDLES:
            attached.setdefault(target, []).append(source)

    node_ids = [_node_field(node, "id") for node in nodes]
    if start_node_id and start_node_id in node_ids:
        stack = [start_node_id]
    else:
        stack = [node_id for node_id in node_ids if node_id not in has_incoming]
    seen = set()
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        stack.extend(outgoing.get(node_id, []))
        stack.extend(attached.get(node_id, []))
    return seen


def train_model_nodes(
    nodes: Optional[Iterable[Any]],
    edges: Optional[Iterable[Dict[str, Any]]] = None,
    start_node_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """The data (configuration) of the Train Model nodes a test turn can run.

    Without edges every Train Model node counts. With them, only those
    reachable from the turn's start, so e.g. resuming a human-in-the-loop
    form after the training step runs in the request as before. A branch the
    turn won't take at run time still counts: that is only known by running.
    """
    nodes = list(nodes or [])
    reachable = _reachable_node_ids(nodes, edges, start_node_id) if edges is not None else None
    found = []
    for node in nodes:
        if _node_field(node, "type") != TRAIN_MODEL_NODE_TYPE:
            continue
        if reachable is not None and _node_field(node, "id") not in reachable:
            continue
        data = _node_field(node, "data")
        found.append(data if isinstance(data, dict) else {})
    return found


def _is_templated(value: Any) -> bool:
    return isinstance(value, str) and "{{" in value


def check_training_config(node_data: Dict[str, Any]) -> None:
    """Refuse a Train Model node whose search settings are out of range or too large.

    Raised as a 400 before a job is queued, rather than failing in the worker
    (TM-17). The node runs the same checks again when it trains.
    """
    from app.modules.workflow.engine.nodes.ml import hyperparameter_optimization as hpo_module
    from app.modules.workflow.engine.nodes.ml import training_checks

    model_type = node_data.get("modelType")
    model_parameters = node_data.get("modelParameters") or {}
    optimization_config = node_data.get("optimizationConfig") or {}
    method = node_data.get("hyperparameterOptimization") or "none"
    # Templated values ({{...}}) are only known at run time; the node checks
    # them once they are resolved.
    if isinstance(optimization_config, dict) and method in hpo_module.VALID_METHODS:
        resolved = {key: value for key, value in optimization_config.items() if not _is_templated(value)}
        # The node's own checks, so a value it would refuse is a 400 here
        # rather than a failed job; then the ranges the dialog allows.
        try:
            training_checks.check_optimization_config(method, resolved)
        except (TypeError, ValueError):
            # A malformed value (e.g. a list as Scoring) is reported by the node itself.
            pass
        training_checks.check_search_limits(method, resolved)
    if not isinstance(model_type, str) or not isinstance(model_parameters, dict) or not isinstance(
        optimization_config, dict
    ):
        return
    try:
        hpo_module.check_search_size(
            model_type.lower(),
            model_parameters,
            method,
            optimization_config,
        )
    except (TypeError, ValueError):
        # A malformed option (e.g. "cvFolds": "three") is reported by the node itself.
        return


def a_train_model_trained(execution_output: Dict[str, Any]) -> bool:
    """Whether any Train Model node in the run finished with a trained model."""
    output = execution_output.get("output")
    # Every Train Model result carries the path of the model it trained.
    if isinstance(output, dict) and output.get("success") is True and "model_file_path" in output:
        return True
    state = execution_output.get("state")
    statuses = state.get("nodeExecutionStatus") if isinstance(state, dict) else None
    if not isinstance(statuses, dict):
        return False
    return any(
        isinstance(entry, dict)
        and entry.get("type") == TRAIN_MODEL_NODE_TYPE
        and entry.get("status") == "success"
        and isinstance(entry.get("output"), dict)
        and entry["output"].get("success") is True
        and "model_file_path" in entry["output"]
        for entry in statuses.values()
    )


def run_failure(result: Any) -> Optional[str]:
    """Why a finished test run failed, or None when it didn't.

    The run returns normally even when a node failed, so the job takes its
    status from the run's response (TM-17). A failed Train Model node fails
    the job with its message unless another Train Model node trained a model
    (the rule ML pipeline runs use), and so does a run whose status is failed.
    """
    if not isinstance(result, dict):
        return None
    failed_nodes = [node for node in result.get("failed_nodes") or [] if isinstance(node, dict)]
    training_failures = [node for node in failed_nodes if node.get("type") == TRAIN_MODEL_NODE_TYPE]
    if training_failures:
        if a_train_model_trained(result):
            return None
        return str(training_failures[0].get("error") or "The Train Model node failed.")
    if result.get("status") == "failed":
        for node in failed_nodes:
            if node.get("error"):
                return str(node["error"])
        return "The test run failed."
    return None


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

# Write the job only if its stored status is still one of ARGV[3..], so the
# user's cancel and the worker's own status writes never overwrite each other.
_SET_IF_STATUS = """
local raw = redis.call('GET', KEYS[1])
if not raw then return false end
local status = cjson.decode(raw)['status']
for i = 3, #ARGV do
    if ARGV[i] == status then
        redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
        return 1
    end
end
return false
"""


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
            if await self._redis.set(key, job_id, ex=ACTIVE_SLOT_TTL_SECONDS, nx=True):
                return await self._create(tenant_id, user_id, kind, job_id), None
            current_id = await self._redis.get(key)
            if current_id is None:
                continue  # expired between the two calls
            current = await self.get(tenant_id, current_id)
            if current is not None and public_view(current)["status"] not in FINISHED_STATUSES:
                return None, current
            if await self._redis.eval(_REPLACE_IF_UNCHANGED, 1, key, current_id, job_id, ACTIVE_SLOT_TTL_SECONDS):
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
        running a job sees the status on its next heartbeat and stops. If the
        job finished in the meantime, its own status stands.
        """
        job = await self.get(tenant_id, job_id)
        if job is None or public_view(job)["status"] in FINISHED_STATUSES:
            return job
        cancelled = await self.update(
            tenant_id,
            job_id,
            expect=(STATUS_QUEUED, STATUS_RUNNING),
            status=STATUS_CANCELLED,
            error=CANCELLED_ERROR,
        )
        return cancelled or await self.get(tenant_id, job_id)

    async def update(
        self, tenant_id: str, job_id: str, expect: Optional[Tuple[str, ...]] = None, **fields: Any
    ) -> Optional[Dict[str, Any]]:
        """Merge fields into the job. With expect, only if its stored status is one of those.

        Returns the updated job, or None if the job is gone or its status
        moved on (e.g. the user cancelled it while the worker finished).
        """
        job = await self.get(tenant_id, job_id)
        if job is None:
            return None
        job.update(fields)
        job["updated_at"] = _now()
        job["heartbeat"] = time.time()
        if expect is None:
            await self._save(tenant_id, job)
            return job
        written = await self._redis.eval(
            _SET_IF_STATUS,
            1,
            job_key(tenant_id, job_id),
            json.dumps(jsonable_encoder(job)),
            settings.ML_TRAINING_JOB_TTL_SECONDS,
            *expect,
        )
        return job if written else None

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
