"""Unit tests for the startup LLM-usage schema verification in migrations.py"""

from unittest.mock import MagicMock

import pytest

import migrations

EVENTS = "llm_usage_events"
RATES = "llm_cost_rates"
CONSTRAINT = migrations.LLM_USAGE_NON_NEGATIVE_CONSTRAINT

HEALTHY_DEF = (
    "CHECK (((input_tokens >= 0) AND (output_tokens >= 0)"
    " AND (total_tokens >= 0) AND (call_index >= 0)"
    " AND (cache_read_tokens >= 0) AND (cache_creation_tokens >= 0)))"
)

_BIGINT_ZERO = ("bigint", True, "'0'::bigint")
_RATE = ("numeric(18,10)", False, None)


def _healthy():
    return {
        EVENTS: {
            "cache_read_tokens": _BIGINT_ZERO,
            "cache_creation_tokens": _BIGINT_ZERO,
            "cache_read_per_1k": _RATE,
            "cache_creation_per_1k": _RATE,
        },
        RATES: {
            "cache_read_per_1k": _RATE,
            "cache_creation_per_1k": _RATE,
        },
    }


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class FakeConnection:
    def __init__(self, columns, constraint):
        self._columns = columns
        self._constraint = constraint
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append(str(statement))
        params = params or {}
        if "name" in params:
            return FakeResult([self._constraint] if self._constraint else [])
        facts = self._columns.get(params["table"], {})
        return FakeResult([(name, *value) for name, value in facts.items()])

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _problems(columns=None, constraint=(HEALTHY_DEF, True)):
    connection = FakeConnection(_healthy() if columns is None else columns, constraint)
    return migrations._llm_usage_schema_problems(connection)


class TestAHealthySchema:
    def test_a_migrated_database_reports_nothing(self):
        assert _problems() == []

    @pytest.mark.parametrize("default", ["'0'::bigint", "0", " 0 "], ids=repr)
    def test_equivalent_zero_defaults_are_all_accepted(self, default):
        columns = _healthy()
        columns[EVENTS]["cache_read_tokens"] = ("bigint", True, default)

        assert _problems(columns) == []

    def test_a_not_valid_marker_on_the_right_definition_is_only_a_validation_problem(self):
        problems = _problems(constraint=(f"{HEALTHY_DEF} NOT VALID", False))

        assert problems == [f"constraint {CONSTRAINT} is not validated"]

    def test_deparser_drift_in_whitespace_and_parentheses_is_tolerated(self):
        drifted = (
            "CHECK ((input_tokens >= 0) AND (output_tokens >= 0)\n"
            "  AND (total_tokens >= 0) AND (call_index >= 0)\n"
            "  AND (cache_read_tokens >= 0) AND (cache_creation_tokens >= 0))"
        )

        assert _problems(constraint=(drifted, True)) == []

    def test_a_future_migration_adding_a_conjunct_still_verifies(self):
        extended = HEALTHY_DEF.replace(
            "(cache_creation_tokens >= 0)))", "(cache_creation_tokens >= 0) AND (new_counter >= 0)))"
        )

        assert _problems(constraint=(extended, True)) == []


class TestMissingObjects:
    def test_a_missing_table_is_reported(self):
        columns = _healthy()
        columns[RATES] = {}

        assert f"table {RATES} is missing" in _problems(columns)

    @pytest.mark.parametrize("column", ["cache_read_tokens", "cache_creation_tokens", "cache_read_per_1k"])
    def test_a_missing_event_column_is_reported(self, column):
        columns = _healthy()
        del columns[EVENTS][column]

        assert f"{EVENTS}.{column} is missing" in _problems(columns)

    def test_a_missing_rates_column_is_reported(self):
        columns = _healthy()
        del columns[RATES]["cache_creation_per_1k"]

        assert f"{RATES}.cache_creation_per_1k is missing" in _problems(columns)


class TestTypeStrictness:
    def test_a_token_column_of_the_wrong_type_is_rejected(self):
        columns = _healthy()
        columns[EVENTS]["cache_read_tokens"] = ("integer", True, "0")

        assert any("expected bigint NOT NULL" in p for p in _problems(columns))

    def test_a_nullable_token_column_is_rejected(self):
        columns = _healthy()
        columns[EVENTS]["cache_creation_tokens"] = ("bigint", False, "0")

        assert any("expected bigint NOT NULL" in p for p in _problems(columns))

    def test_a_token_column_without_its_zero_default_is_rejected(self):
        columns = _healthy()
        columns[EVENTS]["cache_read_tokens"] = ("bigint", True, None)

        assert any("expected 0" in p for p in _problems(columns))

    @pytest.mark.parametrize("wrong", ["numeric(10,2)", "numeric", "double precision"])
    def test_a_rate_column_of_the_wrong_precision_is_rejected(self, wrong):
        columns = _healthy()
        columns[RATES]["cache_read_per_1k"] = (wrong, False, None)

        assert any("expected numeric(18,10) NULL" in p for p in _problems(columns))

    def test_a_non_nullable_rate_column_is_rejected(self):
        columns = _healthy()
        columns[RATES]["cache_creation_per_1k"] = ("numeric(18,10)", True, None)

        assert any("expected numeric(18,10) NULL" in p for p in _problems(columns))

    def test_an_unexpected_rate_default_is_rejected(self):
        columns = _healthy()
        columns[EVENTS]["cache_read_per_1k"] = ("numeric(18,10)", False, "0")

        assert any("unexpected server default" in p for p in _problems(columns))


class TestTheConstraint:
    def test_a_missing_constraint_is_reported(self):
        assert f"constraint {CONSTRAINT} is missing from {EVENTS}" in _problems(constraint=None)

    def test_the_pre_00110_expression_sharing_the_name_is_rejected(self):
        pre_00110 = (
            "CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND (total_tokens >= 0) AND (call_index >= 0)))"
        )

        problems = _problems(constraint=(pre_00110, True))
        assert any("missing non-negative checks for: cache_read_tokens, cache_creation_tokens" in p for p in problems)

    def test_a_wrong_operator_is_rejected(self):
        weakened = HEALTHY_DEF.replace("(cache_read_tokens >= 0)", "(cache_read_tokens > 0)")

        assert any("cache_read_tokens" in p for p in _problems(constraint=(weakened, True)))

    def test_an_or_weakened_rewrite_with_every_substring_present_is_rejected(self):
        weakened = HEALTHY_DEF.replace(" AND ", " OR ")

        problems = _problems(constraint=(weakened, True))
        assert any("not a pure conjunction" in p for p in problems)

    @pytest.mark.parametrize(
        "smuggled",
        [
            "CHECK (CASE WHEN false THEN ((input_tokens >= 0) AND (output_tokens >= 0)"
            " AND (total_tokens >= 0) AND (call_index >= 0)"
            " AND (cache_read_tokens >= 0) AND (cache_creation_tokens >= 0)) ELSE true END)",
            HEALTHY_DEF.replace("CHECK (", "CHECK (NOT NOT ", 1),
            HEALTHY_DEF.replace("(cache_creation_tokens >= 0)", "(cache_creation_tokens >= 0) AND (1 = 1)"),
        ],
        ids=["case-wrapped", "double-negated", "extra-foreign-predicate"],
    )
    def test_non_conjunctive_structure_around_the_predicates_is_rejected(self, smuggled):
        problems = _problems(constraint=(smuggled, True))
        assert any("not a pure conjunction" in p for p in problems)

    def test_an_unvalidated_constraint_is_rejected(self):
        assert _problems(constraint=(HEALTHY_DEF, False)) == [
            f"constraint {CONSTRAINT} is not validated"
        ]

    def test_the_lookup_is_scoped_to_the_table_not_just_the_name(self):
        connection = FakeConnection(_healthy(), (HEALTHY_DEF, True))
        migrations._llm_usage_schema_problems(connection)

        constraint_sql = connection.statements[-1]
        assert "conrelid = to_regclass(:table)" in constraint_sql
        assert "convalidated" in constraint_sql


class TestVerifyLlmUsageSchema:
    def _engine_returning(self, monkeypatch, connection=None, error=None):
        engine = MagicMock()
        if error is not None:
            engine.connect.side_effect = error
        else:
            engine.connect.return_value = connection
        monkeypatch.setattr(migrations, "create_engine", MagicMock(return_value=engine))
        return engine

    def test_a_sound_database_verifies_and_the_engine_is_disposed(self, monkeypatch):
        connection = FakeConnection(_healthy(), (HEALTHY_DEF, True))
        engine = self._engine_returning(monkeypatch, connection)

        assert migrations.verify_llm_usage_schema("postgresql://x/y", "main") is True
        engine.dispose.assert_called_once()

    def test_a_broken_database_fails_and_the_engine_is_still_disposed(self, monkeypatch):
        connection = FakeConnection(_healthy(), None)
        engine = self._engine_returning(monkeypatch, connection)

        assert migrations.verify_llm_usage_schema("postgresql://x/y", "main") is False
        engine.dispose.assert_called_once()

    def test_an_unreachable_database_fails_closed(self, monkeypatch):
        engine = self._engine_returning(monkeypatch, error=OSError("connection refused"))

        assert migrations.verify_llm_usage_schema("postgresql://x/y", "tenant:(acme)") is False
        engine.dispose.assert_called_once()

    def test_the_credentials_in_the_url_never_reach_the_log(self, monkeypatch, caplog):
        self._engine_returning(monkeypatch, error=OSError("connection refused"))
        url = "postgresql+psycopg2://admin:hunter2@db.internal/core_db"

        with caplog.at_level("ERROR"):
            migrations.verify_llm_usage_schema(url, "tenant:(acme)")

        assert "hunter2" not in caplog.text and url not in caplog.text
        assert "tenant:(acme)" in caplog.text
