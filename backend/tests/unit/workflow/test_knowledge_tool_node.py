"""Tests for KnowledgeToolNode: the text the LLM sees and what is recorded on the node run"""

import logging
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.modules.data.providers import KnowledgeSearchError, SearchResult
from app.modules.data.utils.doc import format_search_results
from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes.knowledge_tool_node import KnowledgeToolNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.services.agent_knowledge import KnowledgeBaseService

NODE = {"id": "kb", "type": "knowledgeBaseNode", "data": {"name": "KB"}}
ACME_KB = SimpleNamespace(id="kb-1", name="Acme help centre")
GLOBEX_KB = SimpleNamespace(id="kb-2", name="Globex policies")
SEARCH_ERROR = 'Search failed for knowledge base "Globex policies": vector search failed: embedding model timed out'
RESULTS = [
    SearchResult(
        id="KB:kb-1#article_7",
        content="Refunds\n\nHow refunds work",
        metadata={"name": "Refunds", "article_url": "https://help.example.com/7", "kb_id": "kb-1"},
        score=0.91,
        source="vector",
    ),
    SearchResult(id="KB:kb-1#chunk_2", content="Parking zones", metadata={"kb_id": "kb-1"}, score=0.4, source="legra"),
]


def _node(selected_bases=("kb-1",)):
    node_config = {**NODE, "data": {**NODE["data"], "selectedBases": list(selected_bases), "query": "refund"}}
    state = WorkflowState(
        workflow={"config": {"id": "wf-1"}, "nodes": [node_config], "edges": []},
        thread_id="11111111-1111-1111-1111-111111111111",
        initial_values={"message": "hi"},
    )
    state.start_node_execution("kb")
    return KnowledgeToolNode("kb", node_config, state)


@contextmanager
def _knowledge_bases(found_bases, search):
    knowledge_service = MagicMock(get_by_ids=AsyncMock(return_value=list(found_bases)))
    rag_manager = MagicMock(search=search)
    injector = MagicMock(get=lambda cls: knowledge_service if cls is KnowledgeBaseService else rag_manager)
    with patch("app.dependencies.injector.injector", injector):
        yield rag_manager


def _search_returning(results, found_bases=(ACME_KB,)):
    return _knowledge_bases(found_bases, AsyncMock(return_value=results))


def _search_failing(error, found_bases=(ACME_KB, GLOBEX_KB)):
    return _knowledge_bases(found_bases, AsyncMock(side_effect=error))


def _run_entry(node):
    return node.state.node_execution_status["kb"]


@pytest.mark.asyncio
async def test_llm_text_is_the_formatted_results_and_sources_are_recorded():
    node = _node()
    with _search_returning(RESULTS) as rag_manager:
        text = await node.process({"selectedBases": ["kb-1"], "query": "refund"})

    assert text == format_search_results(RESULTS, include_metadata=False)
    assert rag_manager.search.await_args.kwargs["format_results"] is False
    assert _run_entry(node)["sources"] == [
        {
            "id": "KB:kb-1#article_7",
            "title": "Refunds",
            "score": 0.91,
            "source": "vector",
            "kb_id": "kb-1",
        },
        {"id": "KB:kb-1#chunk_2", "title": None, "score": 0.4, "source": "legra", "kb_id": "kb-1"},
    ]
    assert "warnings" not in _run_entry(node)
    assert "partial_failure" not in _run_entry(node)


@pytest.mark.asyncio
@pytest.mark.parametrize("stored", [None, 0], ids=repr)
async def test_an_empty_stored_limit_searches_with_five(stored):
    with _search_returning(RESULTS) as rag_manager:
        await _node().process({"selectedBases": ["kb-1"], "query": "refund", "limit": stored})

    assert rag_manager.search.await_args.kwargs["limit"] == 5


@pytest.mark.asyncio
async def test_a_set_limit_is_kept():
    with _search_returning(RESULTS) as rag_manager:
        await _node().process({"selectedBases": ["kb-1"], "query": "refund", "limit": 3})

    assert rag_manager.search.await_args.kwargs["limit"] == 3


@pytest.mark.asyncio
async def test_no_results_keeps_the_existing_text():
    node = _node()
    with _search_returning([]):
        text = await node.execute()

    assert text == "No results found."
    assert _run_entry(node)["sources"] == []
    assert _run_entry(node)["status"] == "success"
    assert _run_entry(node)["error"] is None
    assert "warnings" not in _run_entry(node)


@pytest.mark.asyncio
async def test_a_failed_search_fails_the_step_with_the_reason():
    node = _node(["kb-1", "kb-2"])
    with _search_failing(KnowledgeSearchError(SEARCH_ERROR)):
        returned = await node.execute()

    assert is_node_failure(returned)["error"] == f"Error processing knowledge tool: {SEARCH_ERROR}"
    assert _run_entry(node)["status"] == "failed"
    assert SEARCH_ERROR in _run_entry(node)["error"]
    assert "sources" not in _run_entry(node)


@pytest.mark.asyncio
async def test_a_partly_failed_search_returns_the_other_results_and_records_the_error():
    node = _node(["kb-1", "kb-2"])
    with _search_failing(KnowledgeSearchError(SEARCH_ERROR, results=RESULTS)):
        text = await node.execute()

    assert text == format_search_results(RESULTS, include_metadata=False)
    assert _run_entry(node)["status"] == "success"
    assert _run_entry(node)["partial_failure"] == f"Knowledge search incomplete. {SEARCH_ERROR}"
    assert _run_entry(node)["warnings"] == [f"Knowledge search incomplete. {SEARCH_ERROR}"]
    assert [source["id"] for source in _run_entry(node)["sources"]] == ["KB:kb-1#article_7", "KB:kb-1#chunk_2"]

    response = node.state.format_state_as_response()
    assert response["has_failures"] is True
    assert response["failed_nodes"] == [
        {
            "node_id": "kb",
            "name": "KB",
            "type": "knowledgeBaseNode",
            "error": f"Knowledge search incomplete. {SEARCH_ERROR}",
        }
    ]


@pytest.mark.asyncio
async def test_step_fails_when_none_of_the_selected_knowledge_bases_exists():
    node = _node(["kb-8", "kb-9"])
    with _search_returning(RESULTS, found_bases=[]) as rag_manager:
        returned = await node.execute()

    error = is_node_failure(returned)["error"]
    assert error == (
        "Error processing knowledge tool: none of the selected knowledge bases exists any more (ids: kb-8, kb-9)"
    )
    assert _run_entry(node)["status"] == "failed"
    rag_manager.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_knowledge_bases_are_skipped_with_a_warning_naming_them():
    node = _node(["kb-1", "kb-9"])
    with _search_returning(RESULTS, found_bases=[ACME_KB]) as rag_manager:
        text = await node.execute()

    assert text == format_search_results(RESULTS, include_metadata=False)
    assert rag_manager.search.await_args.args[0] == [ACME_KB]
    assert _run_entry(node)["status"] == "success"
    assert _run_entry(node)["warnings"] == ["Knowledge bases not found and skipped: kb-9"]
    assert "partial_failure" not in _run_entry(node)
    assert node.state.format_state_as_response()["failed_nodes"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selected_id",
    ["A3F0C1D2-0000-4000-8000-00000000ABCD", "a3f0c1d2000040008000 00000000abcd".replace(" ", "")],
    ids=["upper case", "no hyphens"],
)
async def test_selected_id_matches_its_knowledge_base_however_it_is_written(selected_id):
    found = SimpleNamespace(id=UUID("a3f0c1d2-0000-4000-8000-00000000abcd"), name="Acme help centre")
    missing_id = "b4a1d2e3-0000-4000-8000-00000000abcd"
    node = _node([selected_id, missing_id])
    with _search_returning(RESULTS, found_bases=[found]):
        await node.execute()

    assert _run_entry(node)["warnings"] == [f"Knowledge bases not found and skipped: {missing_id}"]


@pytest.mark.asyncio
async def test_a_long_failure_text_is_capped_in_the_run_details():
    node = _node(["kb-1", "kb-2"])
    with _search_failing(KnowledgeSearchError("; ".join([SEARCH_ERROR] * 20))):
        await node.execute()

    error = _run_entry(node)["error"]
    assert error.startswith(f"Error processing knowledge tool: {SEARCH_ERROR}")
    assert len(error) < 600
    assert "chars total)" in error


@pytest.mark.asyncio
async def test_a_failed_search_is_logged_once(caplog):
    node = _node(["kb-1", "kb-2"])
    failure = KnowledgeSearchError(SEARCH_ERROR, error_types=["TimeoutError", "TimeoutError"])
    with caplog.at_level(logging.WARNING), _search_failing(failure):
        await node.execute()

    app_lines = [record.getMessage() for record in caplog.records if record.name.startswith("app.")]
    assert app_lines == [f"Error processing knowledge tool: {SEARCH_ERROR} [TimeoutError]"]
    assert "TimeoutError" not in _run_entry(node)["error"]


@pytest.mark.asyncio
async def test_a_partly_failed_search_is_logged_once_with_the_error_type(caplog):
    node = _node(["kb-1", "kb-2"])
    failure = KnowledgeSearchError(SEARCH_ERROR, results=RESULTS, error_types=["TimeoutError"])
    with caplog.at_level(logging.WARNING), _search_failing(failure):
        await node.execute()

    app_lines = [record.getMessage() for record in caplog.records if record.name.startswith("app.")]
    assert app_lines == [f"Knowledge tool kb: Knowledge search incomplete. {SEARCH_ERROR} [TimeoutError]"]
