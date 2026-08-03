"""Unit tests for DuckDuckGo web search."""

from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.utils import web_search_utils
from app.core.utils.web_search_utils import WebSearchError, search_web


def _html_result(href: str, title: str = "Title", snippet: str = "Snippet", extra_class: str = "") -> str:
    return (
        f'<div class="result results_links web-result {extra_class}">'
        f'<h2 class="result__title"><a class="result__a" href="{href}">{title}</a></h2>'
        f'<a class="result__snippet" href="#">{snippet}</a></div>'
    )


def _html_page(*rows: str) -> str:
    return f'<html><body><div id="links">{"".join(rows)}</div></body></html>'


_HTML_SERP = _html_page(
    _html_result(
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdocs&amp;rut=abc",
        title="Example Docs",
        snippet="First <b>snippet</b>",
    ),
    _html_result("https://duckduckgo.com/y.js?ad_provider=x", title="Sponsored", extra_class="result--ad"),
    _html_result("https://direct.example.org/page", title="Direct", snippet="Second snippet"),
)

_LITE_SERP = (
    "<html><body><table>"
    '<tr><td>1.</td><td><a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Flite"'
    ' class="result-link">Lite Result</a></td></tr>'
    '<tr><td></td><td class="result-snippet">Lite snippet here</td></tr>'
    "</table></body></html>"
)

_CHALLENGE_PAGE = (
    '<html><body><div class="anomaly-modal__modal"><form class="challenge-form"></form>'
    "<p>Unfortunately, bots use DuckDuckGo too.</p></div></body></html>"
)

_NO_RESULTS_PAGE = '<html><body><div class="no-results">No  results.</div></body></html>'

_DRIFT_PAGE = '<html><body><div class="brand-new-layout">nothing familiar here</div></body></html>'


@pytest.mark.asyncio
async def test_search_unwraps_uddg_skips_ads_and_ranks(monkeypatch):
    fetch = AsyncMock(return_value=_HTML_SERP)
    monkeypatch.setattr(web_search_utils, "_fetch_serp", fetch)

    results = await search_web("python asyncio")

    assert [r.url for r in results] == ["https://example.com/docs", "https://direct.example.org/page"]
    assert [r.position for r in results] == [1, 2]
    assert results[0].title == "Example Docs"
    assert results[0].snippet == "First snippet"
    assert results[0].domain == "example.com"
    fetch.assert_awaited_once()
    assert fetch.call_args.args[0] == web_search_utils._HTML_ENDPOINT


@pytest.mark.asyncio
async def test_uddg_value_is_not_double_decoded(monkeypatch):
    page = _html_page(_html_result("/l/?uddg=https%3A%2F%2Fexample.com%2Fa%252520b", title="Encoded"))
    monkeypatch.setattr(web_search_utils, "_fetch_serp", AsyncMock(return_value=page))

    results = await search_web("encoded")

    assert results[0].url == "https://example.com/a%2520b"


@pytest.mark.asyncio
async def test_invalid_uddg_destinations_are_skipped(monkeypatch):
    page = _html_page(
        _html_result("/l/?uddg=javascript%3Aalert(1)", title="Bad scheme"),
        _html_result("/l/?uddg=https%3A%2F%2Fuser%3Apass%40evil.example%2F", title="Credentials"),
        _html_result("/l/?uddg=%2Fjust-a-path", title="No host"),
        _html_result("/l/?uddg=https%3A%2F%2Fgood.example.com%2Fok", title="Good"),
    )
    monkeypatch.setattr(web_search_utils, "_fetch_serp", AsyncMock(return_value=page))

    results = await search_web("mixed")

    assert [r.url for r in results] == ["https://good.example.com/ok"]
    assert results[0].position == 1


def test_parse_lite_serp_extracts_title_href_and_snippet():
    entries = web_search_utils._parse_lite_serp(_LITE_SERP)

    assert entries == [
        ("Lite Result", "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Flite", "Lite snippet here")
    ]


@pytest.mark.asyncio
async def test_no_results_marker_returns_empty_without_lite_fallback(monkeypatch):
    fetch = AsyncMock(return_value=_NO_RESULTS_PAGE)
    monkeypatch.setattr(web_search_utils, "_fetch_serp", fetch)

    assert await search_web("gibberish qwertyzxcv") == []
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_challenge_page_stops_ddg_without_lite(monkeypatch):
    fetch = AsyncMock(side_effect=[_CHALLENGE_PAGE, _LITE_SERP])
    monkeypatch.setattr(web_search_utils, "_fetch_serp", fetch)

    with pytest.raises(WebSearchError) as err:
        await search_web("python")

    assert err.value.category == "blocked"
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_ddg_timeout_still_falls_back_to_lite(monkeypatch):
    fetch = AsyncMock(side_effect=[WebSearchError("t", category="timeout"), _LITE_SERP])
    monkeypatch.setattr(web_search_utils, "_fetch_serp", fetch)

    results = await search_web("python")

    assert [call.args[0] for call in fetch.call_args_list] == [
        web_search_utils._HTML_ENDPOINT,
        web_search_utils._LITE_ENDPOINT,
    ]
    assert results[0].url == "https://example.com/lite"
    assert results[0].snippet == "Lite snippet here"


@pytest.mark.asyncio
async def test_selector_drift_is_classified_and_raised(monkeypatch):
    monkeypatch.setattr(web_search_utils, "_fetch_serp", AsyncMock(side_effect=[_DRIFT_PAGE, _DRIFT_PAGE]))

    with pytest.raises(WebSearchError) as err:
        await search_web("python")

    assert err.value.category == "selector_drift"


@pytest.mark.asyncio
async def test_exclude_domains_filter_is_suffix_safe(monkeypatch):
    page = _html_page(
        _html_result("https://example.com/a", title="A"),
        _html_result("https://sub.example.com/b", title="B"),
        _html_result("https://notexample.com/c", title="C"),
    )
    monkeypatch.setattr(web_search_utils, "_fetch_serp", AsyncMock(return_value=page))

    results = await search_web("q", exclude_domains=["example.com"])

    assert [r.domain for r in results] == ["notexample.com"]
    assert results[0].position == 1


@pytest.mark.asyncio
async def test_dedup_strips_fragments_lowercases_host_and_renumbers(monkeypatch):
    page = _html_page(
        _html_result("https://example.com/page#one", title="One"),
        _html_result("https://EXAMPLE.com/page#two", title="Two"),
        _html_result("https://other.example.net/x", title="Other"),
    )
    monkeypatch.setattr(web_search_utils, "_fetch_serp", AsyncMock(return_value=page))

    results = await search_web("q")

    assert [(r.title, r.url, r.position) for r in results] == [
        ("One", "https://example.com/page", 1),
        ("Other", "https://other.example.net/x", 2),
    ]


@pytest.mark.asyncio
async def test_max_results_truncates_and_large_values_are_clamped(monkeypatch):
    page = _html_page(
        _html_result("https://a.example.com/1"),
        _html_result("https://b.example.com/2"),
        _html_result("https://c.example.com/3"),
    )
    monkeypatch.setattr(web_search_utils, "_fetch_serp", AsyncMock(return_value=page))

    assert len(await search_web("q", max_results=1)) == 1
    assert len(await search_web("q", max_results=999)) == 3


@pytest.mark.asyncio
async def test_param_mapping_for_region_time_safesearch_and_site(monkeypatch):
    fetch = AsyncMock(return_value=_HTML_SERP)
    monkeypatch.setattr(web_search_utils, "_fetch_serp", fetch)

    await search_web(
        "genassist platform",
        region="de-de",
        time_range="week",
        safesearch="off",
        include_domain="Example.COM.",
    )

    params = fetch.call_args.args[1]
    assert params["q"] == "genassist platform site:example.com"
    assert params["kl"] == "de-de"
    assert params["df"] == "w"
    assert params["kp"] == "-2"


@pytest.mark.asyncio
async def test_unknown_region_falls_back_and_any_time_range_omits_df(monkeypatch):
    fetch = AsyncMock(return_value=_HTML_SERP)
    monkeypatch.setattr(web_search_utils, "_fetch_serp", fetch)

    await search_web("q", region="zz-nope", time_range="any")

    params = fetch.call_args.args[1]
    assert params["kl"] == "wt-wt"
    assert "df" not in params


@pytest.mark.asyncio
async def test_invalid_config_is_rejected_before_any_fetch(monkeypatch):
    fetch = AsyncMock(return_value=_HTML_SERP)
    monkeypatch.setattr(web_search_utils, "_fetch_serp", fetch)

    cases = [
        {"query": ""},
        {"query": "x" * 401},
        {"query": "q", "include_domain": "not a domain!"},
        {"query": "q", "include_domain": "localhost"},
        {"query": "q", "exclude_domains": [f"d{i}.example.com" for i in range(11)]},
        {"query": "q", "include_domain": "example.com", "exclude_domains": ["example.com"]},
    ]
    for case in cases:
        with pytest.raises(WebSearchError) as err:
            await search_web(case.pop("query"), **case)
        assert err.value.category == "invalid_config"
    fetch.assert_not_awaited()


def _no_dns(monkeypatch):
    monkeypatch.setattr(web_search_utils, "_validate_url", AsyncMock(return_value=None))


def _ok_response() -> httpx.Response:
    return httpx.Response(200, content=b"<html>ok</html>", headers={"content-type": "text/html"})


@pytest.mark.asyncio
async def test_fetch_serp_follows_relative_redirect_on_allowlisted_host(monkeypatch):
    _no_dns(monkeypatch)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if len(seen) == 1:
            return httpx.Response(302, headers={"location": "/html/moved"})
        return _ok_response()

    body = await web_search_utils._fetch_serp(
        web_search_utils._HTML_ENDPOINT, {"q": "x"}, transport=httpx.MockTransport(handler)
    )

    assert body == "<html>ok</html>"
    assert seen[1] == "https://html.duckduckgo.com/html/moved"


@pytest.mark.asyncio
async def test_fetch_serp_rejects_redirect_off_the_allowlist(monkeypatch):
    _no_dns(monkeypatch)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.example.com/serp"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_serp(
            web_search_utils._HTML_ENDPOINT, {"q": "x"}, transport=httpx.MockTransport(handler)
        )

    assert err.value.category == "blocked"
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_fetch_serp_rejects_redirect_with_credentials(monkeypatch):
    _no_dns(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://user:pass@duckduckgo.com/html/"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_serp(
            web_search_utils._HTML_ENDPOINT, {"q": "x"}, transport=httpx.MockTransport(handler)
        )

    assert err.value.category == "blocked"


@pytest.mark.asyncio
async def test_fetch_serp_gives_up_after_max_hops(monkeypatch):
    _no_dns(monkeypatch)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": f"/html/hop{len(seen)}"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_serp(
            web_search_utils._HTML_ENDPOINT, {"q": "x"}, transport=httpx.MockTransport(handler)
        )

    assert "Too many redirects" in str(err.value)
    assert len(seen) == web_search_utils._MAX_REDIRECTS + 1


@pytest.mark.asyncio
async def test_fetch_serp_normalizes_uppercase_and_trailing_dot_hosts(monkeypatch):
    _no_dns(monkeypatch)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if len(seen) == 1:
            return httpx.Response(302, headers={"location": "https://DuckDuckGo.COM./html/x"})
        return _ok_response()

    body = await web_search_utils._fetch_serp(
        web_search_utils._HTML_ENDPOINT, {"q": "x"}, transport=httpx.MockTransport(handler)
    )

    assert body == "<html>ok</html>"
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_fetch_serp_rejects_oversized_body(monkeypatch):
    _no_dns(monkeypatch)
    oversized = b"x" * (web_search_utils._MAX_SERP_BYTES + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=oversized, headers={"content-type": "text/html"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_serp(
            web_search_utils._HTML_ENDPOINT, {"q": "x"}, transport=httpx.MockTransport(handler)
        )

    assert "size limit" in str(err.value)


@pytest.mark.asyncio
async def test_fetch_serp_rejects_non_html_content_type(monkeypatch):
    _no_dns(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{}", headers={"content-type": "application/json"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_serp(
            web_search_utils._HTML_ENDPOINT, {"q": "x"}, transport=httpx.MockTransport(handler)
        )

    assert "non-HTML" in str(err.value)


def test_sanitize_error_strips_urls_and_query_strings():
    exc = RuntimeError("boom at https://duckduckgo.com/html/?q=XYZZY-CANARY-QUERY and ?q=leaky&kl=us-en")

    text = web_search_utils._sanitize_error(exc)

    assert "XYZZY-CANARY-QUERY" not in text
    assert "duckduckgo" not in text
    assert "leaky" not in text
    assert "RuntimeError" in text
    assert web_search_utils._sanitize_error(httpx.ConnectTimeout("t")) == "Timeout contacting search provider"


def _mwmbl_entry(url: str, title: str = "Title", content: str = "Snippet") -> dict:
    return {"url": url, "title": title, "content": content}


def _mwmbl_payload(*entries: dict) -> dict:
    return {"results": list(entries)}


@pytest.mark.asyncio
async def test_search_mwmbl_maps_content_to_snippet_and_caps_two(monkeypatch):
    payload = _mwmbl_payload(
        _mwmbl_entry("https://a.example.com/1", title="A", content="First"),
        _mwmbl_entry("https://b.example.com/2", title="B", content="Second"),
        _mwmbl_entry("https://c.example.com/3", title="C", content="Third"),
    )
    monkeypatch.setattr(web_search_utils, "_fetch_mwmbl", AsyncMock(return_value=payload))

    results = await web_search_utils.search_mwmbl("q")

    assert [(r.title, r.url, r.snippet, r.position) for r in results] == [
        ("A", "https://a.example.com/1", "First", 1),
        ("B", "https://b.example.com/2", "Second", 2),
    ]


@pytest.mark.asyncio
async def test_search_mwmbl_respects_max_results_one(monkeypatch):
    payload = _mwmbl_payload(_mwmbl_entry("https://a.example.com/1"), _mwmbl_entry("https://b.example.com/2"))
    monkeypatch.setattr(web_search_utils, "_fetch_mwmbl", AsyncMock(return_value=payload))

    assert len(await web_search_utils.search_mwmbl("q", max_results=1)) == 1


@pytest.mark.asyncio
async def test_search_mwmbl_skips_malformed_credentialed_and_bad_scheme(monkeypatch):
    payload = _mwmbl_payload(
        _mwmbl_entry("https://good.example.com/ok", title="Good", content="ok"),
        {"title": "Missing url", "content": "x"},
        {"url": "https://x.example.com", "content": "no title"},
        _mwmbl_entry("javascript:alert(1)", title="Bad scheme"),
        _mwmbl_entry("https://user:pass@evil.example/", title="Credentials"),
        _mwmbl_entry("https://good.example.com/ok#dup", title="Dup"),
        _mwmbl_entry("https://second.example.com/ok", title="Second"),
    )
    monkeypatch.setattr(web_search_utils, "_fetch_mwmbl", AsyncMock(return_value=payload))

    results = await web_search_utils.search_mwmbl("q")

    assert [r.url for r in results] == ["https://good.example.com/ok", "https://second.example.com/ok"]
    assert [r.position for r in results] == [1, 2]


@pytest.mark.asyncio
async def test_search_mwmbl_domain_filters_suffix_safe_and_renumber(monkeypatch):
    payload = _mwmbl_payload(
        _mwmbl_entry("https://example.com/a", title="A"),
        _mwmbl_entry("https://sub.example.com/b", title="B"),
        _mwmbl_entry("https://notexample.com/c", title="C"),
    )
    monkeypatch.setattr(web_search_utils, "_fetch_mwmbl", AsyncMock(return_value=payload))

    excluded = await web_search_utils.search_mwmbl("q", exclude_domains=["example.com"])
    assert [r.domain for r in excluded] == ["notexample.com"]
    assert excluded[0].position == 1

    included = await web_search_utils.search_mwmbl("q", include_domain="example.com")
    assert [r.url for r in included] == ["https://example.com/a", "https://sub.example.com/b"]


@pytest.mark.asyncio
async def test_search_mwmbl_filtering_can_yield_zero(monkeypatch):
    payload = _mwmbl_payload(_mwmbl_entry("https://example.com/a"))
    monkeypatch.setattr(web_search_utils, "_fetch_mwmbl", AsyncMock(return_value=payload))

    assert await web_search_utils.search_mwmbl("q", exclude_domains=["example.com"]) == []


@pytest.mark.asyncio
async def test_search_mwmbl_valid_empty_results(monkeypatch):
    monkeypatch.setattr(web_search_utils, "_fetch_mwmbl", AsyncMock(return_value={"results": []}))

    assert await web_search_utils.search_mwmbl("q") == []


@pytest.mark.asyncio
async def test_search_mwmbl_missing_results_key_is_fallback_error(monkeypatch):
    monkeypatch.setattr(web_search_utils, "_fetch_mwmbl", AsyncMock(return_value={"noresults": []}))

    with pytest.raises(WebSearchError) as err:
        await web_search_utils.search_mwmbl("q")
    assert err.value.category == "fallback"


@pytest.mark.asyncio
async def test_search_mwmbl_wrong_top_level_shape_is_fallback_error(monkeypatch):
    monkeypatch.setattr(web_search_utils, "_fetch_mwmbl", AsyncMock(return_value=[1, 2, 3]))

    with pytest.raises(WebSearchError) as err:
        await web_search_utils.search_mwmbl("q")
    assert err.value.category == "fallback"


@pytest.mark.asyncio
async def test_fetch_mwmbl_decodes_json_object(monkeypatch):
    _no_dns(monkeypatch)
    payload = {"results": [{"url": "https://a.example.com/1", "title": "A", "content": "x"}]}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    body = await web_search_utils._fetch_mwmbl("q", transport=httpx.MockTransport(handler))

    assert body == payload


@pytest.mark.asyncio
async def test_fetch_mwmbl_rejects_non_json_content_type(monkeypatch):
    _no_dns(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html/>", headers={"content-type": "text/html"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_mwmbl("q", transport=httpx.MockTransport(handler))
    assert err.value.category == "fallback"


@pytest.mark.asyncio
async def test_fetch_mwmbl_rejects_malformed_json(monkeypatch):
    _no_dns(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{not json", headers={"content-type": "application/json"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_mwmbl("q", transport=httpx.MockTransport(handler))
    assert err.value.category == "fallback"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 429, 500])
async def test_fetch_mwmbl_rejects_non_2xx(monkeypatch, status):
    _no_dns(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"results": []})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_mwmbl("q", transport=httpx.MockTransport(handler))
    assert err.value.category == "fallback"


@pytest.mark.asyncio
async def test_fetch_mwmbl_rejects_redirect(monkeypatch):
    _no_dns(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://api.mwmbl.org/other"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_mwmbl("q", transport=httpx.MockTransport(handler))
    assert err.value.category == "fallback"


@pytest.mark.asyncio
async def test_fetch_mwmbl_maps_timeout(monkeypatch):
    _no_dns(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_mwmbl("q", transport=httpx.MockTransport(handler))
    assert err.value.category == "fallback"


@pytest.mark.asyncio
async def test_fetch_mwmbl_rejects_oversized_body(monkeypatch):
    _no_dns(monkeypatch)
    oversized = b'{"results": []}' + b" " * (web_search_utils._MWMBL_MAX_BYTES + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=oversized, headers={"content-type": "application/json"})

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_mwmbl("q", transport=httpx.MockTransport(handler))
    assert err.value.category == "fallback"


@pytest.mark.asyncio
async def test_fetch_mwmbl_sanitizes_transport_error_and_query(monkeypatch):
    _no_dns(monkeypatch)
    canary = "XYZZY-CANARY-QUERY"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach https://api.mwmbl.org/?q={canary}", request=request)

    with pytest.raises(WebSearchError) as err:
        await web_search_utils._fetch_mwmbl(canary, transport=httpx.MockTransport(handler))

    assert err.value.category == "fallback"
    assert canary not in str(err.value)
