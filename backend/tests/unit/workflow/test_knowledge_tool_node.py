"""Tests for KnowledgeToolNode: the text the LLM sees and the sources recorded on the node run"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.data.providers import SearchResult
from app.modules.data.utils.doc import format_search_results
from app.modules.workflow.engine.nodes.knowledge_tool_node import KnowledgeToolNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.services.agent_knowledge import KnowledgeBaseService

NODE = {"id": "kb", "type": "knowledgeBaseNode", "data": {"name": "KB"}}
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


def _node():
    state = WorkflowState(
        workflow={"config": {"id": "wf-1"}, "nodes": [NODE], "edges": []},
        thread_id="11111111-1111-1111-1111-111111111111",
        initial_values={"message": "hi"},
    )
    state.start_node_execution("kb")
    return KnowledgeToolNode("kb", NODE, state)


@contextmanager
def _search_returning(results):
    knowledge_service = MagicMock(get_by_ids=AsyncMock(return_value=[MagicMock()]))
    rag_manager = MagicMock(search=AsyncMock(return_value=results))
    injector = MagicMock(get=lambda cls: knowledge_service if cls is KnowledgeBaseService else rag_manager)
    with patch("app.dependencies.injector.injector", injector):
        yield rag_manager


@pytest.mark.asyncio
async def test_llm_text_is_the_formatted_results_and_sources_are_recorded():
    node = _node()
    with _search_returning(RESULTS) as rag_manager:
        text = await node.process({"selectedBases": ["kb-1"], "query": "refund"})

    assert text == format_search_results(RESULTS, include_metadata=False)
    assert rag_manager.search.await_args.kwargs["format_results"] is False
    assert node.state.node_execution_status["kb"]["sources"] == [
        {
            "id": "KB:kb-1#article_7",
            "title": "Refunds",
            "score": 0.91,
            "source": "vector",
            "kb_id": "kb-1",
        },
        {"id": "KB:kb-1#chunk_2", "title": None, "score": 0.4, "source": "legra", "kb_id": "kb-1"},
    ]


@pytest.mark.asyncio
async def test_no_results_keeps_the_existing_text():
    node = _node()
    with _search_returning([]):
        text = await node.process({"selectedBases": ["kb-1"], "query": "refund"})

    assert text == "No results found."
    assert node.state.node_execution_status["kb"]["sources"] == []
