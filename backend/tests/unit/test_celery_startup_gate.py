"""Celery refuses to start against a database that cannot record LLM usage"""

import os
import subprocess
import sys
import textwrap

_CELERY_STARTED = 7


def _run_entrypoint(command: str, verified: bool) -> subprocess.CompletedProcess:
    script = textwrap.dedent(
        f"""
        import runpy, sys

        sys.argv = ["run_celery.py", {command!r}]

        import migrations
        migrations.verify_llm_usage_schema_for_all_databases = lambda: {verified!r}

        import celery.__main__
        celery.__main__.main = lambda: sys.exit({_CELERY_STARTED})

        runpy.run_path("run_celery.py", run_name="__main__")
        """
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", ""),
            "CELERY_INCLUDE_ML_TASKS": "false",
            **{
                k: v
                for k, v in os.environ.items()
                if k.startswith(("DB_", "REDIS_", "CELERY_", "DATA_", "OPENAI_", "VECTOR_", "CHROMA_"))
            },
        },
    )


def test_the_worker_refuses_to_start_against_an_unmigrated_schema():
    proc = _run_entrypoint("worker", verified=False)

    assert proc.returncode == 1, f"expected a non-zero exit, got {proc.returncode}\n{proc.stderr[-2000:]}"
    assert proc.returncode != _CELERY_STARTED, "celery must not be reached once the gate fails"


def test_beat_refuses_separately_from_the_worker():
    proc = _run_entrypoint("beat", verified=False)

    assert proc.returncode == 1, f"expected a non-zero exit, got {proc.returncode}\n{proc.stderr[-2000:]}"


def test_a_verified_schema_lets_the_worker_through():
    proc = _run_entrypoint("worker", verified=True)

    assert proc.returncode == _CELERY_STARTED, f"celery was not reached\n{proc.stderr[-2000:]}"


def test_flower_is_never_gated():
    """It records no billing rows, so monitoring stays up while a migration lands"""
    proc = _run_entrypoint("flower", verified=False)

    assert proc.returncode == _CELERY_STARTED, f"flower was gated\n{proc.stderr[-2000:]}"
