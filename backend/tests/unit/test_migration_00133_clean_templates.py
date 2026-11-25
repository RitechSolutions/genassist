"""Unit tests for migration 00133, which cleans stored templates once"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "00133_clean_stored_templates.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_00133", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBind:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def execute(self, statement, params=None):
        if str(statement).lstrip().startswith("UPDATE"):
            self.updates.append(params)
            return SimpleNamespace(rowcount=1)
        return SimpleNamespace(all=lambda: self.rows)


@pytest.fixture
def run_migration(monkeypatch):
    def _run(rows):
        module = _load_migration()
        bind = FakeBind(rows)
        monkeypatch.setattr(module, "op", SimpleNamespace(get_bind=lambda: bind))
        module.upgrade()
        return bind.updates

    return _run


def _slack_graph(app_settings_id, test_input):
    graph = {
        "nodes": [
            {
                "id": "n1",
                "type": "slackMessageNode",
                "data": {"name": "Slack", "app_settings_id": app_settings_id, "channel": "#support"},
            }
        ],
        "edges": [],
    }
    if test_input is not None:
        graph["testInput"] = test_input
    return graph


def test_only_templates_that_change_are_rewritten(run_migration):
    stored = SimpleNamespace(id=uuid4(), graph=_slack_graph(str(uuid4()), {"message": "hi", "api_key": "sk-1"}))
    clean = SimpleNamespace(id=uuid4(), graph=_slack_graph(None, {"message": "hi"}))

    updates = run_migration([stored, clean])

    assert updates == [{"graph": _slack_graph(None, {"message": "hi"}), "id": stored.id}]


def test_a_second_run_changes_nothing(run_migration):
    stored = SimpleNamespace(id=uuid4(), graph=_slack_graph(str(uuid4()), None))
    (update,) = run_migration([stored])

    assert run_migration([SimpleNamespace(id=stored.id, graph=update["graph"])]) == []
