"""Unit tests for how the analytics rebuild reports logs it cannot attribute"""

import logging
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from app.services.analytics_aggregation import AnalyticsAggregationService

STAT_DATE = date(2026, 7, 1)


def _log(raw_response: str):
    return SimpleNamespace(id=uuid4(), conversation_id=uuid4(), raw_response=raw_response, conversation=None)


def test_every_unattributed_log_is_named_in_a_warning(caplog):
    logs = [_log("{ truncated"), _log("[]"), _log('{"agent_id": "[CUSTOMER_TIER]"}')]
    service = AnalyticsAggregationService(None, None)

    with caplog.at_level(logging.WARNING, logger="app.services.analytics_aggregation"):
        agent_buckets, node_buckets, unattributed = service._build_buckets_from_logs(logs, STAT_DATE, {})

    assert (agent_buckets, node_buckets, unattributed) == ({}, {}, 3)
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 3, "one warning per unattributed log, whatever the reason"
    for log in logs:
        assert str(log.id) in caplog.text, "the operator alert is only actionable if each log is named"
    assert str(logs[2].conversation_id) in caplog.text, "an unresolvable agent points at the conversation"
