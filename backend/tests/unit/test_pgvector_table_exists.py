"""The pgvector table check must find a table whose name is longer than PostgreSQL keeps."""

from contextlib import asynccontextmanager

import pytest

from app.modules.data.providers.vector.db.pgvector import PgVectorDB

POSTGRES_NAME_LENGTH = 63
LONG_TABLE_NAME = "vector_store_tenant_acme_chat_01a1d225_ce0f_7abc_8def_0123456789ab_dim1536"


class RecordingConnection:
    """Keeps the statement and parameters of the last query and answers with a fixed value."""

    def __init__(self, answer: bool):
        self.answer = answer
        self.statement = ""
        self.parameters: dict = {}

    async def execute(self, statement, parameters):
        self.statement = str(statement)
        self.parameters = parameters
        return self

    def scalar(self) -> bool:
        return self.answer


class RecordingEngine:
    def __init__(self, connection: RecordingConnection):
        self.connection = connection

    @asynccontextmanager
    async def begin(self):
        yield self.connection


def pgvector_with(connection: RecordingConnection) -> PgVectorDB:
    database = PgVectorDB.__new__(PgVectorDB)
    database.engine = RecordingEngine(connection)
    return database


@pytest.mark.asyncio
async def test_table_check_compares_the_name_the_way_postgres_stores_it():
    connection = RecordingConnection(answer=True)

    found = await pgvector_with(connection)._table_exists(LONG_TABLE_NAME)

    assert len(LONG_TABLE_NAME) > POSTGRES_NAME_LENGTH
    assert found is True
    assert f"left(lower(:table_name), {POSTGRES_NAME_LENGTH})" in connection.statement
    assert connection.parameters == {"table_name": LONG_TABLE_NAME}


@pytest.mark.asyncio
async def test_table_check_reports_a_missing_table():
    connection = RecordingConnection(answer=False)

    assert await pgvector_with(connection)._table_exists(LONG_TABLE_NAME) is False


@pytest.mark.asyncio
async def test_table_check_without_a_connection_reports_missing():
    database = PgVectorDB.__new__(PgVectorDB)
    database.engine = None

    assert await database._table_exists(LONG_TABLE_NAME) is False
