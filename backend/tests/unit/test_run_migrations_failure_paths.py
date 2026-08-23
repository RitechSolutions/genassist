"""run.py refuses to start when migrations fail, and leaves the schema check to the lifespan.

Both migration helpers have a ``return False`` path and run.py used to discard the result,
so a partially-migrated fleet served happily while the recorder swallowed every insert
error. The physical-schema check deliberately does NOT run here: on a fresh database the
tables do not exist yet at this point, so verifying would brick the very first boot.
"""

import os
import subprocess
import sys
import textwrap

_UVICORN_STARTED = 7
_VERIFIER_CALLED = 9


def _drive_run_py() -> dict:
    script = textwrap.dedent(
        f"""
        import runpy, sys
        import migrations, uvicorn

        uvicorn.run = lambda *a, **k: sys.exit({_UVICORN_STARTED})

        def _verifier_must_not_run():
            sys.exit({_VERIFIER_CALLED})

        SCENARIOS = {{
            "main_migration_failed": (False, True),
            "tenant_migration_failed": (True, False),
            "fresh_database": (True, True),
        }}

        for name, (main_ok, tenants_ok) in SCENARIOS.items():
            migrations.run_migrations = lambda url, ok=main_ok: ok
            migrations.run_migrations_for_all_tenants = lambda ok=tenants_ok: ok
            migrations.verify_llm_usage_schema_for_all_databases = _verifier_must_not_run
            try:
                runpy.run_path("run.py", run_name="__main__")
                code = 0
            except SystemExit as exc:
                code = exc.code
            print(f"RESULT {{name}}={{code}}")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", ""),
            **{
                k: v
                for k, v in os.environ.items()
                if k.startswith(("DB_", "REDIS_", "CELERY_", "DATA_", "OPENAI_", "VECTOR_", "CHROMA_"))
            },
        },
    )
    results = dict(
        line[len("RESULT ") :].split("=", 1) for line in proc.stdout.splitlines() if line.startswith("RESULT ")
    )
    assert results, f"run.py produced no scenario results\nstderr tail:\n{proc.stderr[-3000:]}"
    return results


def test_migration_failures_stop_startup_and_a_fresh_database_still_boots():
    results = _drive_run_py()

    assert results["main_migration_failed"] == "1"
    assert results["tenant_migration_failed"] == "1"
    assert results["fresh_database"] == str(_UVICORN_STARTED), (
        "a fresh database stamps head with no tables yet — run.py must still reach the server, "
        f"and must not call the verifier (exit {_VERIFIER_CALLED} means it did)"
    )
