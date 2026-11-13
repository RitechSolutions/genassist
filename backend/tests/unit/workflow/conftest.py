import pytest


@pytest.fixture
def thread_rag_backends(monkeypatch):
    """Fake embedder and vector store behind every per-chat search built in the test."""
    from tests.unit.workflow.thread_rag_fakes import install_fake_backends

    return install_fake_backends(monkeypatch)
