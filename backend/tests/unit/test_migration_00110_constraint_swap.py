"""Unit tests for migration 00110's resumable constraint swap"""

import importlib.util
from pathlib import Path

import pytest

import migrations

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "00110_add_llm_usage_cache_tokens_to_non_negative_check.py"
)

TABLE = "llm_usage_events"
FINAL = "ck_llm_usage_events_non_negative"
TMP = f"{FINAL}__tmp"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_00110", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_migration()


class FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class FakeBind:
    def __init__(self, catalog):
        self._catalog = catalog
        self.queried = []

    def execute(self, statement, params=None):
        name = (params or {})["name"]
        self.queried.append(name)
        return FakeResult(self._catalog.get(name))


class FakeAutocommitBlock:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeContext:
    def autocommit_block(self):
        return FakeAutocommitBlock()


class FakeOp:
    def __init__(self, bind):
        self._bind = bind
        self.executed = []

    def get_bind(self):
        return self._bind

    def get_context(self):
        return FakeContext()

    def execute(self, statement):
        self.executed.append(str(statement))


@pytest.fixture
def swap(monkeypatch, module):
    def _run(catalog, direction="upgrade"):
        bind = FakeBind(catalog)
        fake_op = FakeOp(bind)
        monkeypatch.setattr(module, "op", fake_op)
        getattr(module, direction)()
        return fake_op, bind

    return _run


class TestExpectedDefinitions:
    def test_the_original_definition_is_the_catalog_form(self, module):
        assert module._ORIGINAL_DEF == (
            "CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND (total_tokens >= 0) AND (call_index >= 0)))"
        )

    def test_the_extended_definition_adds_both_cache_counters(self, module):
        assert module._EXTENDED_DEF == (
            "CHECK (((input_tokens >= 0) AND (output_tokens >= 0)"
            " AND (total_tokens >= 0) AND (call_index >= 0)"
            " AND (cache_read_tokens >= 0) AND (cache_creation_tokens >= 0)))"
        )

    def test_the_migration_and_the_runtime_verifier_agree(self, module):
        for column in migrations.LLM_USAGE_NON_NEGATIVE_COLUMNS:
            assert f"({column} >= 0)" in module._EXTENDED_DEF
        assert module._CONSTRAINT == migrations.LLM_USAGE_NON_NEGATIVE_CONSTRAINT

    def test_the_migration_imports_no_application_code(self):
        source = _MIGRATION_PATH.read_text()
        assert "from app" not in source and "import app" not in source
        assert "migrations" not in source.split('"""', 2)[-1]

    def test_normalization_drops_the_not_valid_marker(self, module):
        assert module._normalized(f"{module._EXTENDED_DEF} NOT VALID") == module._EXTENDED_DEF
        assert module._normalized(f"  {module._EXTENDED_DEF}  ") == module._EXTENDED_DEF


class TestUpgradeFromAFreshDatabase:
    def test_the_full_swap_runs_in_order(self, swap, module):
        fake_op, _ = swap({FINAL: (module._ORIGINAL_DEF, True)})

        assert fake_op.executed == [
            f"ALTER TABLE {TABLE} ADD CONSTRAINT {TMP} CHECK ({module._EXTENDED_CHECK}) NOT VALID",
            f"ALTER TABLE {TABLE} DROP CONSTRAINT {FINAL}",
            f"ALTER TABLE {TABLE} VALIDATE CONSTRAINT {TMP}",
            f"ALTER TABLE {TABLE} RENAME CONSTRAINT {TMP} TO {FINAL}",
        ]

    def test_drop_and_validate_are_separate_statements(self, swap, module):
        fake_op, _ = swap({FINAL: (module._ORIGINAL_DEF, True)})

        drop = fake_op.executed.index(f"ALTER TABLE {TABLE} DROP CONSTRAINT {FINAL}")
        validate = fake_op.executed.index(f"ALTER TABLE {TABLE} VALIDATE CONSTRAINT {TMP}")
        assert validate == drop + 1

    def test_the_preflight_reads_both_constraint_names(self, swap, module):
        _, bind = swap({FINAL: (module._ORIGINAL_DEF, True)})

        assert bind.queried == [FINAL, TMP]


class TestUpgradeResumesAPartialSwap:
    def test_resumes_after_the_add(self, swap, module):
        fake_op, _ = swap({FINAL: (module._ORIGINAL_DEF, True), TMP: (module._EXTENDED_DEF, False)})

        assert fake_op.executed == [
            f"ALTER TABLE {TABLE} DROP CONSTRAINT {FINAL}",
            f"ALTER TABLE {TABLE} VALIDATE CONSTRAINT {TMP}",
            f"ALTER TABLE {TABLE} RENAME CONSTRAINT {TMP} TO {FINAL}",
        ]

    def test_resumes_after_the_drop(self, swap, module):
        fake_op, _ = swap({TMP: (module._EXTENDED_DEF, False)})

        assert fake_op.executed == [
            f"ALTER TABLE {TABLE} VALIDATE CONSTRAINT {TMP}",
            f"ALTER TABLE {TABLE} RENAME CONSTRAINT {TMP} TO {FINAL}",
        ]

    def test_resumes_after_the_validate(self, swap, module):
        fake_op, _ = swap({TMP: (module._EXTENDED_DEF, True)})

        assert fake_op.executed == [f"ALTER TABLE {TABLE} RENAME CONSTRAINT {TMP} TO {FINAL}"]

    def test_an_already_swapped_database_is_a_no_op(self, swap, module):
        fake_op, _ = swap({FINAL: (module._EXTENDED_DEF, True)})

        assert fake_op.executed == []


class TestUnrecognizedStatesRefuse:
    @pytest.mark.parametrize(
        "catalog",
        [
            {},
            {FINAL: ("CHECK ((something_else >= 0))", True)},
            {
                FINAL: (
                    "CHECK (((input_tokens >= 0) AND (output_tokens >= 0) AND (total_tokens >= 0) AND (call_index >= 0)))",
                    False,
                )
            },
            {TMP: ("CHECK ((wrong >= 0))", False)},
        ],
        ids=["no constraint at all", "unknown definition", "current constraint unvalidated", "unknown tmp definition"],
    )
    def test_the_swap_refuses_rather_than_guessing(self, swap, catalog):
        with pytest.raises(RuntimeError) as excinfo:
            swap(catalog)

        assert "unrecognised constraint state" in str(excinfo.value)

    def test_the_refusal_reports_what_it_observed(self, swap):
        with pytest.raises(RuntimeError) as excinfo:
            swap({FINAL: ("CHECK ((nonsense))", True)})

        assert "CHECK ((nonsense))" in str(excinfo.value)

    def test_a_leftover_tmp_beside_a_finished_swap_refuses(self, swap, module):
        with pytest.raises(RuntimeError):
            swap({FINAL: (module._EXTENDED_DEF, True), TMP: (module._EXTENDED_DEF, True)})


class TestDowngrade:
    def test_it_swaps_back_to_the_original_definition(self, swap, module):
        fake_op, _ = swap({FINAL: (module._EXTENDED_DEF, True)}, direction="downgrade")

        assert fake_op.executed[0] == (
            f"ALTER TABLE {TABLE} ADD CONSTRAINT {TMP} CHECK ({module._ORIGINAL_CHECK}) NOT VALID"
        )
        assert "cache_read_tokens" not in fake_op.executed[0]

    def test_it_resumes_a_partial_downgrade(self, swap, module):
        fake_op, _ = swap({TMP: (module._ORIGINAL_DEF, True)}, direction="downgrade")

        assert fake_op.executed == [f"ALTER TABLE {TABLE} RENAME CONSTRAINT {TMP} TO {FINAL}"]

    def test_an_already_reverted_database_is_a_no_op(self, swap, module):
        fake_op, _ = swap({FINAL: (module._ORIGINAL_DEF, True)}, direction="downgrade")

        assert fake_op.executed == []

    def test_it_never_reads_or_deletes_rows(self, swap, module):
        fake_op, _ = swap({FINAL: (module._EXTENDED_DEF, True)}, direction="downgrade")

        assert all(sql.startswith("ALTER TABLE") for sql in fake_op.executed)
        assert not any("DELETE" in sql or "SELECT" in sql for sql in fake_op.executed)
