"""Gating shared by the destructive migration drills.

These tests create and drop real schemas, so the safety rule lives in one place rather
than being copied into each module: the connection comes only from
MIGRATION_TEST_DATABASE_URL, never from settings, and the database must be a throwaway.

    ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1 MIGRATION_TEST_DATABASE_URL=postgresql+psycopg2://... \\
        python -m pytest tests/integration/migrations -v

Ordinary runs skip. Under REQUIRE_MIGRATION_TESTS=1 a missing URL or opt-in fails instead,
so a release cannot pass without the drills having run.
"""

import os

import pytest
from sqlalchemy.engine import make_url

_URL = os.environ.get("MIGRATION_TEST_DATABASE_URL", "")
_DESTRUCTIVE_OPT_IN = os.environ.get("ALLOW_DESTRUCTIVE_MIGRATION_TESTS", "") == "1"
_REQUIRED = os.environ.get("REQUIRE_MIGRATION_TESTS", "") == "1"

SKIP_REASON = (
    "Set MIGRATION_TEST_DATABASE_URL to a throwaway database and "
    "ALLOW_DESTRUCTIVE_MIGRATION_TESTS=1 to run the migration drills"
)


def _refuse_unsafe_database(url: str) -> None:
    """These drills rebuild schemas, so they must never point at a real database"""
    database = (make_url(url).database or "").lower()
    if not database:
        pytest.fail("MIGRATION_TEST_DATABASE_URL names no database")
    if "test" not in database:
        pytest.fail(
            f"Refusing to run destructive migration drills against database {database!r}: its name must contain 'test'."
        )


@pytest.fixture(scope="session")
def drill_database_url() -> str:
    if not _URL or not _DESTRUCTIVE_OPT_IN:
        if _REQUIRED:
            pytest.fail(f"REQUIRE_MIGRATION_TESTS=1 but the drills cannot run. {SKIP_REASON}")
        pytest.skip(SKIP_REASON)

    _refuse_unsafe_database(_URL)
    return _URL
