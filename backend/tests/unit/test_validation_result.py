"""Verify ValidationResult remains in a lightweight standalone module."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import textwrap
from dataclasses import fields
from pathlib import Path

from app.modules.integration.database.validation_result import ValidationResult as CanonicalValidationResult

DATABASE_DIR = Path(__file__).resolve().parents[2] / "app" / "modules" / "integration" / "database"
QUERY_VALIDATOR_MOD = "app.modules.integration.database.query_validator"
DATABASE_MANAGER_MOD = "app.modules.integration.database.database_manager"
VALIDATION_RESULT_MOD = "app.modules.integration.database.validation_result"


def test_validation_result_public_shape():
    names = [item.name for item in fields(CanonicalValidationResult)]
    assert names == [
        "is_valid",
        "error_message",
        "warnings",
        "query_type",
        "tables_used",
        "columns_used",
    ]
    result = CanonicalValidationResult(True)
    assert result.is_valid is True
    assert result.error_message is None
    assert result.warnings is None
    assert result.query_type is None
    assert result.tables_used is None
    assert result.columns_used is None

    invalid = CanonicalValidationResult(False, "SQL query is empty.")
    assert invalid.is_valid is False
    assert invalid.error_message == "SQL query is empty."


def test_validation_result_reexports_are_the_same_class():
    from app.modules.integration.database import ValidationResult as PackageValidationResult
    from app.modules.integration.database.query_validator import (
        ValidationResult as ValidatorValidationResult,
    )
    from app.modules.integration.database.read_only_sql import (
        ValidationResult as ReadOnlyValidationResult,
    )

    assert PackageValidationResult is CanonicalValidationResult
    assert ValidatorValidationResult is CanonicalValidationResult
    assert ReadOnlyValidationResult is CanonicalValidationResult


def test_read_only_sql_source_does_not_import_query_validator():
    tree = ast.parse((DATABASE_DIR / "read_only_sql.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert "query_validator" not in imported
    assert not any(
        name is not None and "database_manager" in name for name in imported
    )
    assert "validation_result" in imported


def test_read_only_sql_import_does_not_load_database_manager():
    script = textwrap.dedent(
        f"""
        import sys
        import time

        t0 = time.perf_counter()
        import app.modules.integration.database.read_only_sql  # noqa: F401
        elapsed = time.perf_counter() - t0
        modules = sys.modules
        print("QUERY_VALIDATOR", {QUERY_VALIDATOR_MOD!r} in modules)
        print("DATABASE_MANAGER", {DATABASE_MANAGER_MOD!r} in modules)
        print("VALIDATION_RESULT", {VALIDATION_RESULT_MOD!r} in modules)
        print("MODULE_COUNT", len(modules))
        print("ELAPSED", round(elapsed, 4))
        """
    )
    backend_root = str(DATABASE_DIR.parents[3])
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=backend_root,
        env={**os.environ, "PYTHONPATH": backend_root},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    lines = dict(
        line.split(" ", 1) for line in proc.stdout.splitlines() if " " in line
    )
    assert lines["QUERY_VALIDATOR"] == "False"
    assert lines["DATABASE_MANAGER"] == "False"
    assert lines["VALIDATION_RESULT"] == "True"
    print(proc.stdout)
