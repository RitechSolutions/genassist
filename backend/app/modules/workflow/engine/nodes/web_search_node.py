"""Workflow node: DuckDuckGo search, with optional full-page content fetch."""

import asyncio
import hashlib
import logging
import time
from typing import Any, Dict, List

from app.core.observability import record_web_search_event
from app.core.tenant_scope import get_tenant_context
from app.core.utils.content_relevance import select_relevant_content
from app.core.utils.web_content_utils import extract_main_content
from app.core.utils.web_scrape_cache import get_cached, store
from app.core.utils.web_scraping_utils import fetch_from_url
from app.core.utils.web_search_guard import (
    acquire_global_slot,
    build_request_fingerprint,
    check_enabled,
    check_tenant_rate,
    circuit_is_open,
    get_negative,
    record_block_event,
    single_flight,
    store_negative,
)
from app.core.utils.web_search_utils import (
    _MAX_QUERY_LEN,
    WebSearchError,
    _normalize_domain,
    _sanitize_error,
    search_web,
)
from app.modules.workflow.engine import BaseNode

logger = logging.getLogger(__name__)

_MAX_INCLUDE_DOMAINS = 1
_MAX_EXCLUDE_DOMAINS = 10
_MAX_ENRICH = 5  # top results enriched in advanced depth; not user-scalable
_ENRICH_CONCURRENCY = 3
_ENRICH_PHASE_TIMEOUT = 30  # seconds; slow page fetches are cancelled and those results keep only their snippets
_MAX_DIGEST = 20000
_MAX_WARNINGS = 5
_WARNING_LEN = 200

_KEY_PREFIX = "websearch"
# Bumps the advanced fingerprint when the enrichment selection algorithm changes
_CONTENT_SELECTION_VERSION = "relevance-v1"

# Category-specific messages surfaced when a recent provider failure is remembered.
_NEG_MESSAGES = {
    "blocked": "Web search temporarily unavailable (provider throttling); retry later",
    "timeout": "Web search timed out contacting the provider; retry shortly",
    "selector_drift": "Web search is temporarily unavailable; retry later",
}
# Failure categories that populate the metric outcome directly.
_OUTCOME_CATEGORIES = {"blocked", "timeout", "selector_drift", "invalid_config"}


def _as_int(value: Any, default: int) -> int:
    # config values may arrive as None/""/str/float after template resolution
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


class WebSearchNode(BaseNode):
    """Run a web search and return ranked results plus a short digest for the LLM."""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        query = (config.get("query") or "").strip()
        metric = {"outcome": "error", "rung": "none", "cache": "off", "count": 0}
        try:
            return await self._execute(config, query, started, metric)
        except Exception as exc:
            logger.error("web search node failed unexpectedly: %s", _sanitize_error(exc))
            metric["outcome"] = "error"
            return self._error(query, _sanitize_error(exc))
        finally:
            record_web_search_event(
                metric["outcome"], metric["rung"], metric["cache"], time.perf_counter() - started, metric["count"]
            )

    async def _execute(self, config: Dict[str, Any], query: str, started: float, metric: dict) -> Dict[str, Any]:
        depth = (config.get("searchDepth") or "basic").lower()
        max_results = _clamp(_as_int(config.get("maxResults"), 5), 1, 20)
        max_content_chars = _clamp(_as_int(config.get("maxContentChars"), 2000), 200, 4000)
        max_total = _clamp(_as_int(config.get("maxTotalContentChars"), 8000), 1000, 16000)
        max_age = _clamp(_as_int(config.get("maxAge"), 600), 0, 604800)
        region = (config.get("region") or "wt-wt").strip()
        time_range = (config.get("timeRange") or "any").strip()
        safesearch = (config.get("safeSearch") or "moderate").strip()

        query_digest = hashlib.sha256(query.encode()).hexdigest()[:12]
        logger.debug("web search node start (digest=%s, depth=%s)", query_digest, depth)

        if not query:
            metric["outcome"] = "invalid_config"
            return self._error(query, "Search query is required")
        if len(query) > _MAX_QUERY_LEN:
            metric["outcome"] = "invalid_config"
            return self._error(query, f"Search query exceeds {_MAX_QUERY_LEN} characters")

        try:
            include_domains = self._parse_domains(config.get("includeDomains"))
            exclude_domains = self._parse_domains(config.get("excludeDomains"))
        except WebSearchError as exc:
            metric["outcome"] = "invalid_config"
            return self._error(query, str(exc))
        if len(include_domains) > _MAX_INCLUDE_DOMAINS:
            metric["outcome"] = "invalid_config"
            return self._error(query, "includeDomains supports a single domain in this version")
        if len(exclude_domains) > _MAX_EXCLUDE_DOMAINS:
            metric["outcome"] = "invalid_config"
            return self._error(query, f"excludeDomains supports at most {_MAX_EXCLUDE_DOMAINS} domains")
        include_domain = include_domains[0] if include_domains else ""
        if include_domain and include_domain in exclude_domains:
            metric["outcome"] = "invalid_config"
            return self._error(query, "A domain cannot be both included and excluded")

        # Fingerprint covers every result-affecting option; cache_options mirrors it
        # but carries no raw query, so nothing sensitive reaches Redis keys or logs.
        options = {
            "maxResults": max_results,
            "searchDepth": depth,
            "includeDomain": include_domain,
            "excludeDomains": sorted(exclude_domains),
            "timeRange": time_range,
            "region": region,
            "safeSearch": safesearch,
            "maxContentChars": max_content_chars,
            "maxTotalContentChars": max_total,
        }
        if depth == "advanced":
            # cached envelopes from the old top-of-page truncation must not be
            # served as query-selected content; basic-depth keys are unchanged
            options["contentSelection"] = _CONTENT_SELECTION_VERSION
        fingerprint = build_request_fingerprint(query, options)
        cache_key = f"search:{fingerprint}"
        cache_options = dict(options)

        if not check_enabled():
            metric["outcome"] = "disabled"
            return self._error(query, "Web search is disabled by the administrator")

        if max_age > 0:
            cached = await get_cached(cache_key, cache_options, max_age, key_prefix=_KEY_PREFIX)
            if cached is not None:
                metric.update(outcome=self._hit_outcome(cached), cache="hit", count=cached.get("count", 0))
                return cached

        neg = await get_negative(fingerprint)
        if neg is not None:
            metric.update(outcome="negative_cached", cache="neg")
            return self._error(query, _NEG_MESSAGES.get(neg, "Web search is temporarily unavailable; retry later"))

        if await circuit_is_open():
            metric["outcome"] = "circuit_open"
            return self._error(query, "Web search temporarily unavailable (provider throttling); retry later")

        tenant = get_tenant_context()

        async def producer() -> Dict[str, Any]:
            # Recheck cache, then spend quota and run the full search.
            if max_age > 0:
                again = await get_cached(cache_key, cache_options, max_age, key_prefix=_KEY_PREFIX)
                if again is not None:
                    metric.update(outcome=self._hit_outcome(again), cache="hit", count=again.get("count", 0))
                    return again
            if not await check_tenant_rate(tenant):
                metric["outcome"] = "rate_limited"
                return self._error(query, "Web search rate limit exceeded; retry shortly")
            return await self._search_and_build(
                query=query,
                fingerprint=fingerprint,
                cache_key=cache_key,
                cache_options=cache_options,
                max_age=max_age,
                depth=depth,
                max_results=max_results,
                max_content_chars=max_content_chars,
                max_total=max_total,
                region=region,
                time_range=time_range,
                safesearch=safesearch,
                include_domain=include_domain,
                exclude_domains=exclude_domains,
                metric=metric,
            )

        metric["outcome"] = None
        result = await single_flight(tenant, fingerprint, producer)
        if metric["outcome"] is None:
            metric["outcome"] = self._hit_outcome(result) if result.get("success") else "error"
        metric["count"] = result.get("count", 0)
        if metric["cache"] == "off" and isinstance(result.get("cacheState"), str):
            metric["cache"] = result["cacheState"]
        return result

    async def _search_and_build(
        self,
        *,
        query,
        fingerprint,
        cache_key,
        cache_options,
        max_age,
        depth,
        max_results,
        max_content_chars,
        max_total,
        region,
        time_range,
        safesearch,
        include_domain,
        exclude_domains,
        metric,
    ) -> Dict[str, Any]:
        try:
            async with acquire_global_slot():
                results = await search_web(
                    query,
                    max_results=max_results,
                    region=region,
                    time_range=time_range,
                    safesearch=safesearch,
                    include_domain=include_domain,
                    exclude_domains=exclude_domains,
                )
        except WebSearchError as exc:
            if exc.category in ("blocked", "timeout", "selector_drift"):
                await store_negative(fingerprint, exc.category)
            if exc.category == "blocked":
                await record_block_event()
            metric["outcome"] = exc.category if exc.category in _OUTCOME_CATEGORIES else "error"
            return self._error(query, str(exc))

        serialized = self._serialize(results)
        enriched_count, partial, warnings = 0, False, []
        if depth == "advanced" and serialized:
            enriched_count, partial, warnings = await self._enrich(serialized, query, max_content_chars, max_total)

        envelope: Dict[str, Any] = {
            "success": True,
            "query": query,
            "error": "",
            "count": len(serialized),
            "results": serialized,
            "text": self._build_digest(query, serialized),
            "enrichedCount": enriched_count,
            "partial": partial,
            "warnings": warnings,
        }
        metric.update(outcome="ok" if serialized else "zero", count=len(serialized))

        if max_age > 0:
            await store(cache_key, cache_options, max_age, envelope, key_prefix=_KEY_PREFIX)
            envelope = {**envelope, "cacheState": "miss"}
            metric["cache"] = "miss"
        return envelope

    async def _enrich(
        self, results: List[dict], query: str, max_content_chars: int, max_total: int
    ) -> tuple[int, bool, list]:
        """Fetch full page text into ``content`` for the top results, up to a total size budget.

        Results are filled in rank order. Each page gets at most ``max_content_chars``,
        holding its most query-relevant sections, and only while the shared total budget remains. 
        Fetches run a few at a time with an overall timeout. If a page fails, isn't HTML, times out,
        or has no budget left, it keeps only its snippet and ``partial`` is set to True.
        """
        candidates = results[: min(_MAX_ENRICH, len(results))]
        budgets: dict[int, int] = {}
        remaining = max_total
        for idx in range(len(candidates)):
            if remaining <= 0:
                break
            budget = min(max_content_chars, remaining)
            budgets[idx] = budget
            remaining -= budget

        semaphore = asyncio.Semaphore(_ENRICH_CONCURRENCY)

        async def _fetch_one(idx: int, budget: int) -> tuple[int, str | None]:
            async with semaphore:
                # use_http_request routes through the shared SSRF/IP guard on arbitrary result URLs
                fetched = await fetch_from_url(candidates[idx]["url"], use_http_request=True)
                if not fetched.ok or "html" not in (fetched.content_type or "").lower():
                    return idx, None
                markdown, _ = extract_main_content(fetched.html, candidates[idx]["url"])
                return idx, select_relevant_content(markdown, query, budget)

        tasks = [asyncio.create_task(_fetch_one(idx, budget)) for idx, budget in budgets.items()]
        enriched = fetch_failures = 0
        timed_out = 0
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=_ENRICH_PHASE_TIMEOUT)
            timed_out = len(pending)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                try:
                    idx, content = task.result()
                except Exception:
                    fetch_failures += 1
                    continue
                if content:
                    candidates[idx]["content"] = content
                    enriched += 1
                else:
                    fetch_failures += 1

        budget_skipped = len(candidates) - len(budgets)
        partial = enriched < len(candidates)
        warnings: list[str] = []
        if fetch_failures:
            warnings.append(f"{fetch_failures} of {len(candidates)} pages could not be fetched; snippets kept")
        if timed_out:
            warnings.append(f"{timed_out} page(s) timed out; snippets kept")
        if budget_skipped:
            warnings.append(f"{budget_skipped} page(s) skipped; content budget reached")
        warnings = [w[:_WARNING_LEN] for w in warnings[:_MAX_WARNINGS]]
        return enriched, partial, warnings

    @staticmethod
    def _serialize(results) -> List[dict]:
        return [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "content": "",
                "position": r.position,
                "domain": r.domain,
            }
            for r in results
        ]

    @staticmethod
    def _build_digest(query: str, results: List[dict]) -> str:
        """Numbered, LLM-ready digest; numbering matches each result's position."""
        if not results:
            return f'No results found for: "{query}"'
        blocks = []
        for r in results:
            block = f"{r['position']}. {r['title']}\n   URL: {r['url']}"
            if r.get("snippet"):
                block += f"\n   {r['snippet']}"
            if r.get("content"):
                block += f"\n   {r['content']}"
            blocks.append(block)
        return "\n\n".join(blocks)[:_MAX_DIGEST]

    @staticmethod
    def _hit_outcome(envelope: Dict[str, Any]) -> str:
        return "ok" if envelope.get("count") else "zero"

    @staticmethod
    def _parse_domains(raw: Any) -> List[str]:
        """Split a comma-separated domain field into normalized domains; raises on bad syntax."""
        items = [part.strip() for part in str(raw or "").split(",") if part.strip()]
        return [_normalize_domain(item) for item in items]

    @staticmethod
    def _error(query: str, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "query": query,
            "error": message,
            "count": 0,
            "results": [],
            "text": f"Web search failed: {message}",
            "enrichedCount": 0,
            "partial": False,
            "warnings": [],
        }
