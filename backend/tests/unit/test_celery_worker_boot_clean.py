"""Regression guard for the prefork Celery workers.

Both Celery workers run the prefork pool, which fork()s child processes. ML libraries
(torch / sklearn / transformers / sentence_transformers / faiss) spawn native OpenMP/MKL
threads at import; if they are loaded in the prefork *master* process, fork() copies
their locked mutexes into children -> SIGSEGV.

So the master must import every task module WITHOUT loading any of those libraries, on
the "default" worker (CELERY_INCLUDE_ML_TASKS=false) and on the "ml" worker
(CELERY_INCLUDE_ML_TASKS=true) alike. This test boots the worker app exactly as
run_celery.py does (create_celery() + import_default_modules()) in a *subprocess* (a clean
interpreter — this test process is already polluted by other tests' imports), and asserts
none of the heavy ML libs ended up in sys.modules.

If this fails, some module reachable from a non-ML task's import graph started importing an
ML lib at module top level again. Find it with:
    python -c "import builtins,traceback,os; _o=builtins.__import__; \\
      def h(n,*a,**k):
        ...                       # print stack when n.split('.')[0] in the ML set
"
and move that import to be lazy (inside the function/method that uses it).
"""
import os
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize(
    "worker, include_ml_tasks",
    [("default", "false"), ("ml", "true")],
)
def test_worker_master_imports_no_ml_libs(worker, include_ml_tasks):
    script = textwrap.dedent(
        """
        import sys
        ML = {"torch", "sklearn", "transformers", "sentence_transformers", "faiss", "xgboost", "chromadb"}
        import run_celery
        # Exactly what the Celery worker master does at startup: import all task modules.
        run_celery.celery_app.loader.import_default_modules()
        bad = sorted(ML & {m.split(".")[0] for m in sys.modules})
        print("LOADED:" + ",".join(bad))
        sys.exit(1 if bad else 0)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ.get("PATH", ""),
            # Minimal env so settings load; the worker never connects during import.
            **{k: v for k, v in os.environ.items()
               if k.startswith(("DB_", "REDIS_", "CELERY_", "DATA_", "OPENAI_", "VECTOR_", "CHROMA_"))},
            # Explicit values last so the host environment cannot override them
            "CELERY_INCLUDE_ML_TASKS": include_ml_tasks,
            "CELERY_WORKER_POOL": "prefork",
        },
    )
    loaded = next((l for l in proc.stdout.splitlines() if l.startswith("LOADED:")), "LOADED:?")
    assert proc.returncode == 0, (
        f"prefork {worker}-worker master loaded ML libs at boot ({loaded}). "
        f"Move the offending top-level import to be lazy.\nstderr tail:\n{proc.stderr[-2000:]}"
    )