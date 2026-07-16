"""Web search via DuckDuckGo HTML pages, with a keyless Mwmbl fallback.

Tries ``html.duckduckgo.com/html/`` first, then falls back to
``lite.duckduckgo.com/lite/``. Search-page fetches use a dedicated httpx client.
Redirects are followed manually and only to an allowlisted set of DuckDuckGo hosts.
Result links are unwrapped from DDG's ``uddg`` redirect, safety-checked, and skipped if unsafe.

``search_mwmbl`` is a separate, entry point used by the node only when DDG
explicitly restricts us; it hits a single fixed JSON endpoint and reuses the same
result normalization. It has no provider abstraction and no region/date/safe-search support.
"""

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.utils.web_scraping_utils import _validate_url

logger = logging.getLogger(__name__)

_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"
_LITE_ENDPOINT = "https://lite.duckduckgo.com/lite/"
# Exact hosts only — no suffix matching — so a redirect can never leave DuckDuckGo.
_SERP_HOST_ALLOWLIST = frozenset({"html.duckduckgo.com", "lite.duckduckgo.com", "duckduckgo.com", "www.duckduckgo.com"})
_SERP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_SERP_TIMEOUT = 10  # seconds
_MAX_REDIRECTS = 5
_MAX_SERP_BYTES = 2 * 1024 * 1024  # stream-enforced body cap
_MAX_SERP_URL_LEN = 2048
_MAX_QUERY_LEN = 400
_MAX_TITLE_LEN = 300
_MAX_SNIPPET_LEN = 500
_MAX_RESULTS_CAP = 20
_MAX_EXCLUDE_DOMAINS = 10
_MAX_ERROR_LEN = 500

_MWMBL_ENDPOINT = "https://api.mwmbl.org/api/v2/search/"
_MWMBL_HOST = "api.mwmbl.org"
_MWMBL_HEADERS = {"Accept": "application/json", "User-Agent": "GenAssist-WebSearch/1.0"}
_MWMBL_TIMEOUT = 10  # seconds
_MWMBL_MAX_BYTES = 1024 * 1024
_MWMBL_MAX_RESULTS = 2  # hard ceiling on fallback results, regardless of the caller's maxResults
_FALLBACK_CATEGORY = "fallback"  # internal WebSearchError category for any Mwmbl failure

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_TIME_RANGE_MAP = {"any": "", "day": "d", "week": "w", "month": "m", "year": "y"}
_SAFESEARCH_MAP = {"strict": "1", "moderate": "-1", "off": "-2"}
_DEFAULT_REGION = "wt-wt"
_REGION_ALLOWLIST = frozenset(
    {
        "wt-wt",
        "us-en",
        "uk-en",
        "ca-en",
        "au-en",
        "in-en",
        "za-en",
        "de-de",
        "fr-fr",
        "es-es",
        "it-it",
        "nl-nl",
        "pl-pl",
        "pt-pt",
        "br-pt",
        "mx-es",
        "ar-es",
        "se-sv",
        "no-no",
        "dk-da",
        "fi-fi",
        "tr-tr",
        "gr-el",
        "ru-ru",
        "jp-jp",
        "kr-kr",
        "cn-zh",
        "hk-tzh",
        "tw-tzh",
        "id-en",
        "sg-en",
        "th-en",
        "vn-en",
    }
)

# Strings seen on DuckDuckGo's bot-check page. That page returns HTTP 200, so we detect it by content.
_BLOCK_MARKERS = ("anomaly-modal", "challenge-form", "bots use duckduckgo")
# Empty-result markers: the HTML endpoint uses a ``no-results`` div; the lite endpoint uses plain text.
_NO_RESULTS_MARKERS = ("no-results", "no results", "no more results")

_DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")
_URL_LIKE_RE = re.compile(r"(?:https?:)?//\S+|[?&][\w%+=&.~-]+", re.IGNORECASE)


class WebSearchError(ValueError):

    def __init__(self, message: str, *, category: str = "error") -> None:
        super().__init__(message)
        self.category = category


@dataclass
class SearchResult:

    title: str
    url: str
    snippet: str
    domain: str
    position: int


class WebSearchResultItem(TypedDict):
    """One serialized hit in a node envelope; ``content`` is filled only by advanced enrichment."""

    title: str
    url: str
    snippet: str
    content: str
    position: int
    domain: str


class WebSearchEnvelope(TypedDict):
    """Public web-search node output. Cache keys are added by the cache layer, not the node."""

    success: bool
    query: str
    error: str
    count: int
    results: list[WebSearchResultItem]
    text: str
    enrichedCount: int
    partial: bool
    warnings: list[str]
    cacheState: NotRequired[str]
    cachedAt: NotRequired[float]


def _sanitize_error(exc: Exception) -> str:
    """Render an exception without URL-like substrings or query strings."""
    if isinstance(exc, httpx.TimeoutException):
        return "Timeout contacting search provider"
    text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    return _URL_LIKE_RE.sub("<redacted>", text)[:_MAX_ERROR_LEN]


def _normalize_domain(raw: str) -> str:
    """Normalize a user-supplied domain entry; raises ``invalid_config`` on bad syntax."""
    value = (raw or "").strip().lower()
    if "://" in value:
        value = urlparse(value).hostname or ""
    elif "/" in value:
        value = value.split("/", 1)[0]
    value = value.removesuffix(".")
    if not value or len(value) > 253 or "@" in value or not _DOMAIN_RE.match(value):
        raise WebSearchError("Invalid domain in search configuration", category="invalid_config")
    return value


def _matches_domains(host: str, domains: Sequence[str]) -> bool:
    """Suffix-safe match: ``example.com`` covers ``sub.example.com`` but not ``notexample.com``."""
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _resolve_result_url(href: str) -> str | None:
    """Turn a DuckDuckGo ``/l/?uddg=`` redirect into the real URL, or keep a direct http(s) link."""
    href = (href or "").strip()
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlparse(href)
        host = (parsed.hostname or "").lower()
        is_ddg_link = (host.endswith("duckduckgo.com") or (not host and parsed.path.startswith("/l/"))) and (
            "uddg=" in parsed.query
        )
        if is_ddg_link:
            values = parse_qs(parsed.query).get("uddg")
            if not values:
                return None
            candidate = values[0]
        elif parsed.scheme in ("http", "https"):
            candidate = href
        else:
            return None
        destination = urlparse(candidate)
        if destination.scheme not in ("http", "https") or not destination.hostname:
            return None
        if destination.username or destination.password:
            return None
        return candidate
    except ValueError:
        return None


def _normalize_result_url(url: str) -> str:
    """Lowercase the host and strip the fragment so dedup keys are stable."""
    parsed = urlparse(url)
    return parsed._replace(netloc=parsed.netloc.lower(), fragment="").geturl()


def _is_blocked_page(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in _BLOCK_MARKERS)


def _has_no_results_marker(html: str) -> bool:
    collapsed = " ".join(html.lower().split())
    return any(marker in collapsed for marker in _NO_RESULTS_MARKERS)


def _parse_html_serp(html: str) -> list[tuple[str, str, str]]:
    """Extract (title, href, snippet) rows from the html rung, skipping ads."""
    soup = BeautifulSoup(html, "lxml")
    entries: list[tuple[str, str, str]] = []
    for result in soup.select("div.result"):
        if "result--ad" in (result.get("class") or []):
            continue
        anchor = result.select_one("a.result__a")
        href = anchor.get("href") if anchor else None
        if not href or "y.js" in href:
            continue
        snippet_el = result.select_one(".result__snippet")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        entries.append((anchor.get_text(" ", strip=True), href, snippet))
    return entries


def _parse_lite_serp(html: str) -> list[tuple[str, str, str]]:
    """Extract rows from the lite rung's table layout; the snippet sits on the next row."""
    soup = BeautifulSoup(html, "lxml")
    entries: list[tuple[str, str, str]] = []
    for anchor in soup.select("a.result-link"):
        href = anchor.get("href")
        if not href or "y.js" in href:
            continue
        snippet = ""
        row = anchor.find_parent("tr")
        next_row = row.find_next_sibling("tr") if row else None
        if next_row is not None:
            cell = next_row.select_one("td.result-snippet")
            if cell is not None:
                snippet = cell.get_text(" ", strip=True)
        entries.append((anchor.get_text(" ", strip=True), href, snippet))
    return entries


async def _validate_serp_url(url: str) -> None:
    """Per-hop guard: scheme, no credentials, exact-host allowlist, then the IP/DNS check."""
    if len(url) > _MAX_SERP_URL_LEN:
        raise WebSearchError("Search request URL exceeds the maximum length", category="blocked")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise WebSearchError("Search redirect used a disallowed scheme", category="blocked")
    if parsed.username or parsed.password:
        raise WebSearchError("Search redirect contained credentials", category="blocked")
    host = (parsed.hostname or "").lower().removesuffix(".")
    if host not in _SERP_HOST_ALLOWLIST:
        raise WebSearchError("Search redirect left the allowed provider hosts", category="blocked")
    try:
        await _validate_url(url)
    except ValueError as exc:
        raise WebSearchError("Search provider address failed safety validation", category="blocked") from exc


def _decode_body(data: bytes, charset: str | None) -> str:
    try:
        return data.decode(charset or "utf-8", errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


async def _fetch_serp(url: str, params: dict[str, str], *, transport: httpx.AsyncBaseTransport | None = None) -> str:
    """Fetch one search-results page, following redirects by hand."""
    current = str(httpx.URL(url, params=params))
    try:
        async with httpx.AsyncClient(
            follow_redirects=False, headers=_SERP_HEADERS, timeout=_SERP_TIMEOUT, transport=transport
        ) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                await _validate_serp_url(current)
                async with client.stream("GET", current) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location", "")
                        if not location:
                            raise WebSearchError("Search provider redirect had no destination")
                        current = urljoin(current, location)
                        continue
                    if response.status_code in (403, 429):
                        raise WebSearchError(
                            f"Search provider blocked the request (HTTP {response.status_code})", category="blocked"
                        )
                    if not (200 <= response.status_code < 300):
                        raise WebSearchError(f"Search provider returned HTTP {response.status_code}")
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                        raise WebSearchError("Search provider returned a non-HTML response")
                    chunks: list[bytes] = []
                    received = 0
                    async for chunk in response.aiter_bytes():
                        received += len(chunk)
                        if received > _MAX_SERP_BYTES:
                            raise WebSearchError("Search provider response exceeded the size limit")
                        chunks.append(chunk)
                    return _decode_body(b"".join(chunks), response.charset_encoding)
            raise WebSearchError("Too many redirects from search provider", category="blocked")
    except httpx.TimeoutException as exc:
        raise WebSearchError("Timeout contacting search provider", category="timeout") from exc
    except httpx.HTTPError as exc:
        raise WebSearchError(_sanitize_error(exc)) from exc


def _build_results(
    entries: list[tuple[str, str, str]], *, max_results: int, exclude_domains: Sequence[str]
) -> list[SearchResult]:
    """Unwrap, validate, filter, dedupe, truncate, then renumber positions 1..N."""
    results: list[SearchResult] = []
    seen: set[str] = set()
    for title, href, snippet in entries:
        candidate = _resolve_result_url(href)
        if candidate is None:
            continue
        url = _normalize_result_url(candidate)
        host = urlparse(url).hostname or ""
        if _matches_domains(host, exclude_domains):
            continue
        if url in seen:
            continue
        seen.add(url)
        results.append(
            SearchResult(
                title=title.strip()[:_MAX_TITLE_LEN],
                url=url,
                snippet=snippet.strip()[:_MAX_SNIPPET_LEN],
                domain=host,
                position=0,
            )
        )
        if len(results) == max_results:
            break
    for position, result in enumerate(results, start=1):
        result.position = position
    return results


def _combined_category(categories: Sequence[str]) -> str:
    for category in ("blocked", "timeout", "selector_drift"):
        if category in categories:
            return category
    return "error"


async def search_web(
    query: str,
    *,
    max_results: int = 5,
    region: str = _DEFAULT_REGION,
    time_range: str = "any",
    safesearch: str = "moderate",
    include_domain: str = "",
    exclude_domains: Sequence[str] = (),
) -> list[SearchResult]:
    """Search DuckDuckGo and return up to ``max_results`` ranked hits."""
    query = (query or "").strip()
    if not query:
        raise WebSearchError("Search query is required", category="invalid_config")
    if len(query) > _MAX_QUERY_LEN:
        raise WebSearchError(f"Search query exceeds {_MAX_QUERY_LEN} characters", category="invalid_config")
    try:
        max_results = max(1, min(int(max_results), _MAX_RESULTS_CAP))
    except (TypeError, ValueError):
        raise WebSearchError("maxResults must be a number", category="invalid_config") from None

    include = _normalize_domain(include_domain) if (include_domain or "").strip() else ""
    excludes = [_normalize_domain(domain) for domain in exclude_domains if str(domain).strip()]
    if len(excludes) > _MAX_EXCLUDE_DOMAINS:
        raise WebSearchError(
            f"excludeDomains supports at most {_MAX_EXCLUDE_DOMAINS} domains", category="invalid_config"
        )
    if include and include in excludes:
        raise WebSearchError("A domain cannot be both included and excluded", category="invalid_config")

    params = {
        "q": f"{query} site:{include}" if include else query,
        "kl": region if region in _REGION_ALLOWLIST else _DEFAULT_REGION,
        "kp": _SAFESEARCH_MAP.get(safesearch, _SAFESEARCH_MAP["moderate"]),
    }
    date_filter = _TIME_RANGE_MAP.get(time_range, "")
    if date_filter:
        params["df"] = date_filter
    if len(str(httpx.URL(_HTML_ENDPOINT, params=params))) > _MAX_SERP_URL_LEN:
        raise WebSearchError("Search request URL exceeds the maximum length", category="invalid_config")

    failures: list[tuple[str, WebSearchError]] = []
    for rung, endpoint, parse in (
        ("html", _HTML_ENDPOINT, _parse_html_serp),
        ("lite", _LITE_ENDPOINT, _parse_lite_serp),
    ):
        try:
            page = await _fetch_serp(endpoint, params)
            entries = parse(page)
            if not entries:
                if _is_blocked_page(page):
                    raise WebSearchError("Search provider served a challenge page", category="blocked")
                if _has_no_results_marker(page):
                    return []
                raise WebSearchError("No results parsed; provider markup may have changed", category="selector_drift")
            return _build_results(entries, max_results=max_results, exclude_domains=excludes)
        except WebSearchError as exc:
            failures.append((rung, exc))
            logger.warning("web search rung %s failed (%s): %s", rung, exc.category, exc)
            if exc.category == "blocked":
                raise
        except Exception as exc:  # any rung surprise (parse crash, odd payload) falls to the next rung
            wrapped = WebSearchError(_sanitize_error(exc))
            failures.append((rung, wrapped))
            logger.warning("web search rung %s failed unexpectedly: %s", rung, wrapped)

    detail = "; ".join(f"{rung}: {exc}" for rung, exc in failures)
    raise WebSearchError(
        f"Web search failed on all providers ({detail})"[:_MAX_ERROR_LEN],
        category=_combined_category([exc.category for _, exc in failures]),
    )


async def _fetch_mwmbl(query: str, *, transport: httpx.AsyncBaseTransport | None = None) -> Any:
    """Request one Mwmbl v2 JSON response. On failure, raise a sanitized ``WebSearchError``. """
    url = str(httpx.URL(_MWMBL_ENDPOINT, params={"q": query}))
    if urlparse(url).hostname != _MWMBL_HOST:
        raise WebSearchError("Fallback provider host is not allowed", category=_FALLBACK_CATEGORY)
    try:
        await _validate_url(url)  # shared SSRF / IP / DNS guard on the fixed endpoint
    except ValueError as exc:
        raise WebSearchError("Fallback provider address failed safety validation", category=_FALLBACK_CATEGORY) from exc
    try:
        async with httpx.AsyncClient(
            follow_redirects=False, headers=_MWMBL_HEADERS, timeout=_MWMBL_TIMEOUT, transport=transport
        ) as client:
            async with client.stream("GET", url) as response:
                if response.status_code in _REDIRECT_STATUSES:
                    raise WebSearchError("Fallback provider redirected", category=_FALLBACK_CATEGORY)
                if not (200 <= response.status_code < 300):
                    raise WebSearchError(
                        f"Fallback provider returned HTTP {response.status_code}", category=_FALLBACK_CATEGORY
                    )
                if "application/json" not in response.headers.get("content-type", ""):
                    raise WebSearchError("Fallback provider returned a non-JSON response", category=_FALLBACK_CATEGORY)
                chunks: list[bytes] = []
                received = 0
                async for chunk in response.aiter_bytes():
                    received += len(chunk)
                    if received > _MWMBL_MAX_BYTES:
                        raise WebSearchError(
                            "Fallback provider response exceeded the size limit", category=_FALLBACK_CATEGORY
                        )
                    chunks.append(chunk)
        try:
            return json.loads(b"".join(chunks))
        except (ValueError, UnicodeDecodeError) as exc:
            raise WebSearchError("Fallback provider returned malformed JSON", category=_FALLBACK_CATEGORY) from exc
    except httpx.TimeoutException as exc:
        raise WebSearchError("Timeout contacting fallback provider", category=_FALLBACK_CATEGORY) from exc
    except httpx.HTTPError as exc:
        raise WebSearchError(_sanitize_error(exc), category=_FALLBACK_CATEGORY) from exc


def _normalize_mwmbl_results(
    payload: Any, *, max_results: int, include: str, exclude_domains: Sequence[str]
) -> list[SearchResult]:
    """Turn Mwmbl JSON entries into ``SearchResult`` objects; skip bad ones.

    Domain include/exclude filters run here on normalized hosts (Mwmbl has no
    ``site:`` query). At most two results are kept. A valid
    response with nothing usable is an empty success; a wrong top-level JSON
    shape is a fallback failure.
    """
    if not isinstance(payload, dict):
        raise WebSearchError("Fallback provider returned an unexpected response shape", category=_FALLBACK_CATEGORY)
    raw = payload.get("results")
    if not isinstance(raw, list):
        raise WebSearchError("Fallback provider response was missing results", category=_FALLBACK_CATEGORY)
    limit = min(max_results, _MWMBL_MAX_RESULTS)
    results: list[SearchResult] = []
    seen: set[str] = set()
    for entry in raw:
        if len(results) >= limit:
            break
        if not isinstance(entry, dict):
            continue
        title, url_raw, content = entry.get("title"), entry.get("url"), entry.get("content")
        if not isinstance(title, str) or not isinstance(url_raw, str):
            continue
        candidate = _resolve_result_url(url_raw)  # rejects credentials, non-http(s), empties
        if candidate is None:
            continue
        url = _normalize_result_url(candidate)
        host = urlparse(url).hostname or ""
        if include and not _matches_domains(host, [include]):
            continue
        if exclude_domains and _matches_domains(host, exclude_domains):
            continue
        if url in seen:
            continue
        seen.add(url)
        results.append(
            SearchResult(
                title=title.strip()[:_MAX_TITLE_LEN],
                url=url,
                snippet=(content.strip()[:_MAX_SNIPPET_LEN] if isinstance(content, str) else ""),
                domain=host,
                position=0,
            )
        )
    for position, result in enumerate(results, start=1):
        result.position = position
    return results


async def search_mwmbl(
    query: str,
    *,
    max_results: int = 5,
    include_domain: str = "",
    exclude_domains: Sequence[str] = (),
) -> list[SearchResult]:
    """Fallback search via the Mwmbl community index. Returns at most two hits."""
    query = (query or "").strip()
    if not query:
        raise WebSearchError("Search query is required", category="invalid_config")
    if len(query) > _MAX_QUERY_LEN:
        raise WebSearchError(f"Search query exceeds {_MAX_QUERY_LEN} characters", category="invalid_config")
    try:
        max_results = max(1, min(int(max_results), _MAX_RESULTS_CAP))
    except (TypeError, ValueError):
        raise WebSearchError("maxResults must be a number", category="invalid_config") from None
    include = _normalize_domain(include_domain) if (include_domain or "").strip() else ""
    excludes = [_normalize_domain(domain) for domain in exclude_domains if str(domain).strip()]
    payload = await _fetch_mwmbl(query)
    return _normalize_mwmbl_results(payload, max_results=max_results, include=include, exclude_domains=excludes)
