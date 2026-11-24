"""What a turn's knowledge searches found, and whether an article is among it.

Pure: reads the run's step entries, no DB, engine or LLM.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.services.evaluation_text import normalize_text

KNOWLEDGE_SEARCH_NODE_TYPES = frozenset({"knowledgebasenode", "knowledgetoolnode"})
# The most article names one fact lists; the rest are counted.
MAX_LISTED_ARTICLES = 10

NO_SEARCH = "No knowledge search ran on this turn."
SEARCH_FAILED = "The knowledge search failed on this turn."
NO_ARTICLES = "The knowledge search found no articles."


def knowledge_searches(node_status: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The knowledge searches of one turn in the order they ran, each with the articles it found, best first."""
    runs = [
        (step_id, run)
        for step_id, run in (node_status or {}).items()
        if isinstance(run, dict) and _is_knowledge_search(run)
    ]
    runs.sort(key=lambda item: item[1].get("startTime") or 0)
    return [_search(step_id, run) for step_id, run in runs]


def article_fact(
    wanted: List[str], searches: List[Dict[str, Any]], within_first: Optional[int] = None
) -> Tuple[bool, str]:
    """Whether one of the wanted articles is among what the searches found, and what was seen."""
    if not searches:
        return False, NO_SEARCH
    match = _best_match(wanted, searches)
    if match is None:
        return False, _found_instead(wanted, searches)
    rank, article = match
    found = f'The knowledge search found "{_display_name(article)}" as result {rank}'
    is_too_low = within_first is not None and rank > within_first
    if is_too_low:
        return False, f"{found}, {_outside_first(within_first)}."
    return True, f"{found}."


def within_first_phrase(within_first: Optional[int]) -> str:
    """How a sentence says the article has to be among the first results."""
    if within_first is None:
        return ""
    return " as the first result" if within_first == 1 else f" in the first {within_first} results"


def _is_knowledge_search(run: Dict[str, Any]) -> bool:
    return str(run.get("type") or "").lower() in KNOWLEDGE_SEARCH_NODE_TYPES


def _search(step_id: str, run: Dict[str, Any]) -> Dict[str, Any]:
    sources = run.get("sources")
    found = sources if isinstance(sources, list) else []
    return {
        "step": step_id,
        "label": run.get("name"),
        "failed": run.get("status") == "failed" or bool(run.get("error")),
        "articles": [_article(source) for source in found if isinstance(source, dict)],
    }


def _article(source: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": source.get("id"), "title": source.get("title"), "score": source.get("score")}


def _best_match(wanted: List[str], searches: List[Dict[str, Any]]) -> Optional[Tuple[int, Dict[str, Any]]]:
    """The wanted article at its best position over every search, counted from 1."""
    matches = [
        (rank, article)
        for search in searches
        for rank, article in enumerate(search.get("articles") or [], 1)
        if any(_is_article(article, name) for name in wanted)
    ]
    return min(matches, key=lambda match: match[0], default=None)


def _is_article(article: Dict[str, Any], wanted: str) -> bool:
    """By title or id; the id also without its knowledge-base part, which differs between environments."""
    article_id = str(article.get("id") or "")
    own_id = article_id.partition("#")[2]
    names = {_folded(article.get("title")), _folded(article_id), _folded(own_id)} - {""}
    return _folded(wanted) in names


def _folded(value: Any) -> str:
    return " ".join(normalize_text(value).split()).casefold()


def _display_name(article: Dict[str, Any]) -> str:
    return normalize_text(article.get("title")) or normalize_text(article.get("id"))


def _found_instead(wanted: List[str], searches: List[Dict[str, Any]]) -> str:
    """What the searches found when the wanted article is not among it."""
    found = list(dict.fromkeys(
        _display_name(article) for search in searches for article in search.get("articles") or []
    ))
    if not found:
        every_search_failed = all(search.get("failed") for search in searches)
        return SEARCH_FAILED if every_search_failed else NO_ARTICLES
    missed = _listed([normalize_text(name) for name in wanted])
    return f"The knowledge search did not find {missed}. It found: {_listed(found)}."


def _listed(names: List[str]) -> str:
    """Names in quotes; past the most one fact lists, the rest are counted."""
    quoted = ", ".join(f'"{name}"' for name in names[:MAX_LISTED_ARTICLES])
    more = len(names) - MAX_LISTED_ARTICLES
    return f"{quoted} and {more} more" if more > 0 else quoted


def _outside_first(within_first: int) -> str:
    return "not as the first result" if within_first == 1 else f"not in the first {within_first} results"
