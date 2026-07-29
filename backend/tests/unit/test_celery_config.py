"""Locks the LLM usage slice of the Celery task and beat configuration"""

import pytest

from app import create_celery


@pytest.fixture(scope="module")
def celery_conf():
    return create_celery().conf


def test_only_the_backfill_task_module_is_included(celery_conf):
    assert sorted(m for m in celery_conf.include if "llm_usage" in m) == ["app.tasks.backfill_llm_usage_tasks"]


def test_no_llm_usage_task_is_scheduled(celery_conf):
    """The backfill is operator-triggered, so nothing in this area runs on a timer"""
    beat = celery_conf.beat_schedule or {}
    assert [name for name, entry in beat.items() if "llm_usage" in str(entry.get("task", ""))] == []
