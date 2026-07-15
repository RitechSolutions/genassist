"""Tests for WebSearchNode.process().

Covers: always-same response shape and never raising; check order (feature off,
caches, circuit breaker, rate limit); advanced mode page fetches within a size
budget; and that the raw query never appears in logs or cache keys.
"""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.utils.web_search_utils import SearchResult, WebSearchError
from app.modules.workflow.engine.nodes import web_search_node
from app.modules.workflow.engine.nodes.web_search_node import WebSearchNode

_ENVELOPE_KEYS = {"success", "query", "error", "count", "results", "text", "enrichedCount", "partial", "warnings"}


def _make_node():
    config = {"type": "webSearchNode", "data": {"name": "Web Search"}}
    return WebSearchNode("n1", config, SimpleNamespace())


def _results(n=3):
    return [
        SearchResult(title=f"T{i}", url=f"https://ex{i}.com/p", snippet=f"S{i}", domain=f"ex{i}.com", position=i)
        for i in range(1, n + 1)
    ]


def _html_page(ok=True, content_type="text/html", html="<p>body</p>"):
    return SimpleNamespace(ok=ok, content_type=content_type, html=html)


@pytest.fixture
def guards(monkeypatch):
    """Patch every Redis/cache/provider boundary in the node module with safe defaults."""
    mocks = SimpleNamespace(
        search_web=AsyncMock(return_value=_results()),
        get_cached=AsyncMock(return_value=None),
        store=AsyncMock(),
        get_negative=AsyncMock(return_value=None),
        circuit_is_open=AsyncMock(return_value=False),
        check_tenant_rate=AsyncMock(return_value=True),
        store_negative=AsyncMock(),
        record_block_event=AsyncMock(),
        check_enabled=lambda: True,
        fetch_from_url=AsyncMock(return_value=_html_page()),
        extract_main_content=lambda html, url: ("A" * 5000, "<html/>"),
    )
    for name in vars(mocks):
        monkeypatch.setattr(web_search_node, name, getattr(mocks, name))
    return mocks


@pytest.mark.asyncio
async def test_missing_query_returns_config_error(guards):
    result = await _make_node().process({})
    assert result["success"] is False
    assert result["error"] == "Search query is required"
    assert set(result) == _ENVELOPE_KEYS
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_oversized_query_rejected(guards):
    result = await _make_node().process({"query": "x" * 401})
    assert result["success"] is False
    assert "exceeds" in result["error"]
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_multiple_include_domains_rejected(guards):
    result = await _make_node().process({"query": "q", "includeDomains": "a.com, b.com"})
    assert result["success"] is False
    assert result["error"] == "includeDomains supports a single domain in this version"
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_too_many_exclude_domains_rejected(guards):
    excludes = ",".join(f"d{i}.com" for i in range(11))
    result = await _make_node().process({"query": "q", "excludeDomains": excludes})
    assert result["success"] is False
    assert "at most 10" in result["error"]


@pytest.mark.asyncio
async def test_domain_in_both_lists_rejected(guards):
    result = await _make_node().process(
        {"query": "q", "includeDomains": "example.com", "excludeDomains": "example.com"}
    )
    assert result["success"] is False
    assert result["error"] == "A domain cannot be both included and excluded"


@pytest.mark.asyncio
async def test_invalid_domain_syntax_rejected(guards):
    result = await _make_node().process({"query": "q", "includeDomains": "not a domain!"})
    assert result["success"] is False
    assert "Invalid domain" in result["error"]
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_basic_success_digest_positions_and_cache_store(guards):
    result = await _make_node().process({"query": "genassist"})

    assert result["success"] is True
    assert result["count"] == 3
    assert result["enrichedCount"] == 0
    assert result["partial"] is False
    assert result["warnings"] == []
    assert all(r["content"] == "" for r in result["results"])
    assert [r["position"] for r in result["results"]] == [1, 2, 3]
    assert result["text"].startswith("1. T1")
    assert "URL: https://ex1.com/p" in result["text"]
    assert "3. T3" in result["text"]
    guards.store.assert_awaited_once()
    assert result["cacheState"] == "miss"
    assert "cacheState" not in guards.store.call_args.args[3]


@pytest.mark.asyncio
async def test_zero_hit_envelope(guards):
    guards.search_web.return_value = []
    result = await _make_node().process({"query": "asdfqwerty"})

    assert result["success"] is True
    assert result["count"] == 0
    assert result["results"] == []
    assert result["text"] == 'No results found for: "asdfqwerty"'
    assert result["enrichedCount"] == 0


@pytest.mark.asyncio
async def test_advanced_enriches_all_successes_under_even_split(guards):
    guards.search_web.return_value = _results(6)
    node = _make_node()

    result = await node.process(
        {"query": "q", "searchDepth": "advanced", "maxContentChars": 2000, "maxTotalContentChars": 8000}
    )

    assert result["enrichedCount"] == 5
    assert result["partial"] is False
    assert not any("budget" in w for w in result["warnings"])
    assert all(len(r["content"]) <= 1600 for r in result["results"][:5])
    assert sum(len(r["content"]) for r in result["results"]) <= 8000
    assert result["results"][5]["content"] == ""


@pytest.mark.asyncio
async def test_advanced_failed_page_does_not_waste_budget(guards):
    results = _results(5)
    guards.search_web.return_value = results

    async def _fetch(url, use_http_request=False):
        if url == results[0].url:
            raise RuntimeError("connection reset")
        return _html_page()

    guards.fetch_from_url.side_effect = _fetch

    result = await _make_node().process(
        {"query": "q", "searchDepth": "advanced", "maxContentChars": 2000, "maxTotalContentChars": 8000}
    )

    assert result["enrichedCount"] == 4
    assert result["partial"] is True
    assert result["results"][0]["content"] == ""
    assert all(r["content"] != "" for r in result["results"][1:5])
    assert not any("budget" in w for w in result["warnings"])
    assert any("could not be fetched" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_advanced_empty_extraction_counted_unavailable(guards, monkeypatch):
    monkeypatch.setattr(web_search_node, "extract_main_content", lambda html, url: ("   ‍  ", "<html/>"))

    result = await _make_node().process({"query": "q", "searchDepth": "advanced"})

    assert result["enrichedCount"] == 0
    assert result["partial"] is True
    assert all(r["content"] == "" for r in result["results"])
    assert any("could not be fetched" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_advanced_per_page_failure_and_non_html_degrade_to_snippet(guards):
    results = _results(3)
    guards.search_web.return_value = results

    async def _fetch(url, use_http_request=False):
        if url == results[0].url:
            raise RuntimeError("connection reset")
        if url == results[1].url:
            return _html_page(content_type="application/pdf")
        return _html_page()

    guards.fetch_from_url.side_effect = _fetch

    result = await _make_node().process({"query": "q", "searchDepth": "advanced"})

    assert result["success"] is True
    assert result["enrichedCount"] == 1
    assert result["partial"] is True
    assert any("could not be fetched" in w for w in result["warnings"])
    assert result["results"][0]["content"] == ""
    assert result["results"][1]["content"] == ""
    assert result["results"][2]["content"] != ""


_RELEVANT_PAGE = (
    "# Acme Store\n\n"
    + "The committee archives general notes and routine updates quietly. " * 12
    + "\n\n## Shipping Rates\n\nOvernight shipping costs $42 for domestic orders.\n\n"
    + "The committee reviews general notes and routine updates quietly. " * 12
)


@pytest.mark.asyncio
async def test_advanced_content_prefers_query_relevant_sections(guards, monkeypatch):
    monkeypatch.setattr(web_search_node, "extract_main_content", lambda html, url: (_RELEVANT_PAGE, "<html/>"))

    result = await _make_node().process(
        {"query": "overnight shipping costs", "searchDepth": "advanced", "maxContentChars": 400}
    )

    content = result["results"][0]["content"]
    assert "$42" in content
    assert "committee" not in content
    assert len(content) <= 400
    assert result["enrichedCount"] == 3


@pytest.mark.asyncio
async def test_advanced_content_falls_back_without_query_signal(guards):
    result = await _make_node().process({"query": "q", "searchDepth": "advanced"})

    assert result["results"][0]["content"] == "A" * 2000


@pytest.mark.asyncio
async def test_advanced_options_include_content_selection_marker(guards):
    await _make_node().process({"query": "q", "searchDepth": "advanced"})
    assert guards.get_cached.call_args.args[1]["contentSelection"] == "relevance-v2"

    guards.get_cached.reset_mock()
    await _make_node().process({"query": "q"})
    assert "contentSelection" not in guards.get_cached.call_args.args[1]


@pytest.mark.asyncio
async def test_numeric_clamps_and_maxage_default(guards):
    await _make_node().process({"query": "q", "maxResults": 999})

    assert guards.search_web.call_args.kwargs["max_results"] == 20
    assert guards.get_cached.call_args.args[2] == 600


@pytest.mark.asyncio
async def test_kill_switch_short_circuits(guards, monkeypatch):
    monkeypatch.setattr(web_search_node, "check_enabled", lambda: False)
    result = await _make_node().process({"query": "q"})

    assert result["success"] is False
    assert result["error"] == "Web search is disabled by the administrator"
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_rate_limited_returns_failure_without_search(guards):
    guards.check_tenant_rate.return_value = False
    result = await _make_node().process({"query": "q"})

    assert result["success"] is False
    assert "rate limit" in result["error"]
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_circuit_open_returns_failure_without_search(guards):
    guards.circuit_is_open.return_value = True
    result = await _make_node().process({"query": "q"})

    assert result["success"] is False
    assert "throttling" in result["error"]
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_negative_cache_hit_returns_failure_without_search(guards):
    guards.get_negative.return_value = "blocked"
    result = await _make_node().process({"query": "q"})

    assert result["success"] is False
    assert "throttling" in result["error"]
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_positive_cache_hit_short_circuits(guards):
    cached = {"success": True, "count": 2, "results": [], "text": "cached", "cacheState": "hit"}
    guards.get_cached.return_value = cached
    result = await _make_node().process({"query": "q"})

    assert result is cached
    guards.search_web.assert_not_awaited()


@pytest.mark.asyncio
async def test_websearcherror_maps_to_failure_and_records_block(guards):
    guards.search_web.side_effect = WebSearchError("blocked on all providers", category="blocked")
    result = await _make_node().process({"query": "q"})

    assert result["success"] is False
    assert result["error"] == "blocked on all providers"
    assert set(result) == _ENVELOPE_KEYS
    guards.store_negative.assert_awaited_once()
    assert guards.store_negative.call_args.args[1] == "blocked"
    guards.record_block_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_generic_search_exception_never_raises(guards):
    guards.search_web.side_effect = RuntimeError("unexpected")
    result = await _make_node().process({"query": "q"})

    assert result["success"] is False
    assert set(result) == _ENVELOPE_KEYS


@pytest.mark.asyncio
async def test_unexpected_error_swallowed_preserving_query(guards):
    guards.get_cached.side_effect = RuntimeError("cache backend down")
    result = await _make_node().process({"query": "keepme"})

    assert result["success"] is False
    assert result["query"] == "keepme"
    assert set(result) == _ENVELOPE_KEYS


@pytest.mark.asyncio
async def test_log_hygiene_query_never_logged_or_used_as_key(guards, caplog):
    canary = "XYZZY-CANARY-QUERY"

    with caplog.at_level(logging.DEBUG):
        # provider failure path
        guards.search_web.side_effect = WebSearchError("provider blocked", category="blocked")
        await _make_node().process({"query": canary})
        # cache-backend failure path (node's own except)
        guards.get_cached.side_effect = RuntimeError("redis down")
        await _make_node().process({"query": canary})

    assert canary not in caplog.text
    # cache-key material is the hashed fingerprint, never the raw query
    key = guards.get_cached.call_args_list[0].args[0]
    assert key.startswith("search:")
    assert canary not in key
    assert canary not in str(guards.get_cached.call_args_list[0])
