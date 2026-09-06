"""Locks the Celery task, delivery, and beat configuration"""

import pytest

from app import create_celery
from app.core.config.settings import settings


@pytest.fixture(scope="module")
def celery_conf():
    return create_celery().conf


def test_only_the_backfill_task_module_is_included(celery_conf):
    assert sorted(m for m in celery_conf.include if "llm_usage" in m) == ["app.tasks.backfill_llm_usage_tasks"]


def test_no_llm_usage_task_is_scheduled(celery_conf):
    """The backfill is operator-triggered, so nothing in this area runs on a timer"""
    beat = celery_conf.beat_schedule or {}
    assert [name for name, entry in beat.items() if "llm_usage" in str(entry.get("task", ""))] == []


def test_messages_are_acknowledged_only_after_the_task_finishes(celery_conf):
    """A worker killed mid-task must leave its message in the queue for redelivery"""
    assert celery_conf.task_acks_late is True
    assert celery_conf.task_reject_on_worker_lost is True


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


def test_redelivery_delay_sits_between_task_timeout_and_reconciler(celery_conf):
    """Redelivery must never duplicate a running 2h job, and must precede the reconciler"""
    two_hours = 2 * 60 * 60
    visibility_timeout = celery_conf.broker_transport_options["visibility_timeout"]

    assert visibility_timeout > two_hours
    assert visibility_timeout < settings.TEST_RUN_RUNNING_MAX_AGE_SECONDS
    assert visibility_timeout < settings.WORKFLOW_SCHEDULE_RUNNING_MAX_AGE_SECONDS
