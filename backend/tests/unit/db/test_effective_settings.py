"""Unit tests for the startup report of the effective statement timeout"""

import logging
from collections import namedtuple
from contextlib import asynccontextmanager

import pytest

from app.db import effective_settings
from app.db.effective_settings import log_effective_statement_timeout

Row = namedtuple("Row", "setting reset_val source")


class _Result:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class FakeAsyncEngine:
    def __init__(self, row=None, error=None):
        self._row = row
        self._error = error

    @asynccontextmanager
    async def connect(self):
        if self._error:
            raise self._error
        yield self

    async def execute(self, _statement):
        return _Result(self._row)


@pytest.mark.asyncio
async def test_logs_configured_effective_and_server_default_with_source(caplog, monkeypatch):
    monkeypatch.setattr(effective_settings.settings, "DB_STATEMENT_TIMEOUT", 1800)
    engine = FakeAsyncEngine(row=Row(setting="1800000", reset_val="73000", source="session"))

    with caplog.at_level(logging.INFO, logger=effective_settings.__name__):
        await log_effective_statement_timeout(engine)

    assert "configured=1800s effective=1800.0s source=session server_default=73.0s" in caplog.text


@pytest.mark.asyncio
async def test_connection_failure_only_warns(caplog):
    engine = FakeAsyncEngine(error=ConnectionError("database unreachable"))

    with caplog.at_level(logging.WARNING, logger=effective_settings.__name__):
        await log_effective_statement_timeout(engine)

    assert "Could not read the effective statement_timeout" in caplog.text
    assert "database unreachable" in caplog.text
