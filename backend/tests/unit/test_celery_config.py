"""Locks the Celery task, delivery, and beat configuration"""

import importlib
import math
import re
from pathlib import Path

import pytest

import app
from app import LONG_TASK_TIMEOUTS, create_celery
from app.core.config.settings import settings

TASK_DECORATOR = re.compile(r"@shared_task(\((.*?)\))?\s*\ndef\s+(\w+)\s*\(", re.S)
TIMEOUT_LITERAL = re.compile(r"timeout\s*=\s*([0-9][0-9 *+]*)")
ML_TASK_MODULES = (
    "app.tasks.ml_model_pipeline_tasks",
    "app.tasks.test_suite_tasks",
    "app.tasks.workflow_schedule_tasks",
)
RUN_TASKS = ("execute_test_suite_run", "execute_workflow_run", "execute_pipeline_run")


@pytest.fixture(scope="module")
def celery_app():
    return create_celery()


@pytest.fixture(scope="module")
def celery_conf(celery_app):
    return celery_app.conf


def test_only_the_backfill_task_module_is_included(celery_conf):
    assert sorted(m for m in celery_conf.include if "llm_usage" in m) == ["app.tasks.backfill_llm_usage_tasks"]


def test_no_llm_usage_task_is_scheduled(celery_conf):
    """The backfill is operator-triggered, so nothing in this area runs on a timer"""
    beat = celery_conf.beat_schedule or {}
    assert [name for name, entry in beat.items() if "llm_usage" in str(entry.get("task", ""))] == []


def test_messages_are_acknowledged_only_after_the_task_finishes(celery_conf):
    """A worker killed mid-task must leave its message in the queue for redelivery"""
    assert celery_conf.task_acks_late is True


def test_a_job_that_kills_its_child_process_is_not_requeued(celery_conf):
    """Requeueing a deterministic crash would jam the queue in an endless loop"""
    assert celery_conf.task_reject_on_worker_lost is False


def _arithmetic(expression: str) -> int:
    return sum(
        math.prod(int(factor) for factor in term.split("*"))
        for term in expression.replace(" ", "").split("+")
    )


def _internal_task_timeouts(included_modules):
    """(task name, internal asyncio timeout) for every included task module that declares one"""
    tasks_dir = Path(app.__file__).parent / "tasks"
    for path in sorted(tasks_dir.glob("*.py")):
        if f"app.tasks.{path.stem}" not in included_modules:
            continue
        source = path.read_text()
        decorators = list(TASK_DECORATOR.finditer(source))
        for index, match in enumerate(decorators):
            decorator_args, function = match.group(2) or "", match.group(3)
            explicit_name = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", decorator_args)
            name = explicit_name.group(1) if explicit_name else f"app.tasks.{path.stem}.{function}"
            body_end = decorators[index + 1].start() if index + 1 < len(decorators) else len(source)
            timeout = TIMEOUT_LITERAL.search(source[match.end():body_end])
            if timeout:
                yield name, _arithmetic(timeout.group(1))


def test_every_task_with_a_long_internal_timeout_has_its_own_limit(celery_conf):
    """The table must mirror the task modules, so no long task slips to the global limit"""
    included_modules = set(celery_conf.include) | set(ML_TASK_MODULES)
    long_tasks = {
        name: timeout
        for name, timeout in _internal_task_timeouts(included_modules)
        if timeout >= celery_conf.task_soft_time_limit
    }

    assert long_tasks
    for name, timeout in long_tasks.items():
        assert LONG_TASK_TIMEOUTS.get(name) == timeout, name


def test_reconcilers_run_on_the_default_queue(celery_conf):
    """The cleanup must never queue behind the ml jam it is meant to clear"""
    assert "app.tasks.run_reconciliation_tasks" in celery_conf.include
    assert not [name for name in celery_conf.task_routes if "reconcile_stuck" in name]

    beat = celery_conf.beat_schedule or {}
    reconcile_tasks = [
        entry["task"] for name, entry in beat.items() if name.startswith("reconcile-stuck")
    ]
    assert reconcile_tasks == [
        "app.tasks.run_reconciliation_tasks.reconcile_stuck_workflow_runs",
        "app.tasks.run_reconciliation_tasks.reconcile_stuck_test_runs",
    ]


def test_long_tasks_get_time_limits_above_their_own_timeout(celery_conf):
    """Under prefork the limits are enforced, so they must never cut a healthy long job"""
    visibility_timeout = celery_conf.broker_transport_options["visibility_timeout"]
    annotations = celery_conf.task_annotations

    assert set(annotations) == set(LONG_TASK_TIMEOUTS)
    for name, timeout in LONG_TASK_TIMEOUTS.items():
        limits = annotations[name]
        assert timeout < limits["soft_time_limit"] < limits["time_limit"] < visibility_timeout
    for run_task in RUN_TASKS:
        assert LONG_TASK_TIMEOUTS[run_task] == 2 * 60 * 60


def test_global_time_limit_covers_every_task_without_its_own(celery_conf):
    """Every task outside the table has an internal timeout of at most 5 minutes"""
    assert 5 * 60 < celery_conf.task_soft_time_limit < celery_conf.task_time_limit


def test_every_time_limited_task_name_is_a_registered_task(celery_app):
    """A misspelled name here would silently leave that task on the global limit"""
    celery_app.loader.import_default_modules()
    for module in ML_TASK_MODULES:
        importlib.import_module(module)

    assert set(LONG_TASK_TIMEOUTS) <= set(celery_app.tasks)


def test_frequent_scheduled_ticks_expire_before_the_next_one(celery_conf):
    """A tick that missed its slot is dropped instead of queuing behind a long ml job"""
    beat = celery_conf.beat_schedule or {}
    for name in (
        "check-scheduled-pipeline-runs",
        "check-scheduled-workflow-runs",
        "reconcile-stuck-workflow-runs",
        "reconcile-stuck-test-runs",
    ):
        entry = beat[name]
        assert entry["options"]["expires"] < entry["schedule"], name


def test_redelivery_delay_sits_between_task_timeout_and_reconciler(celery_conf):
    """Redelivery must never duplicate a running 2h job, and must precede the reconciler"""
    two_hours = 2 * 60 * 60
    visibility_timeout = celery_conf.broker_transport_options["visibility_timeout"]

    assert visibility_timeout > two_hours
    assert visibility_timeout < settings.TEST_RUN_RUNNING_MAX_AGE_SECONDS
    assert visibility_timeout < settings.WORKFLOW_SCHEDULE_RUNNING_MAX_AGE_SECONDS
