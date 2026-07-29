"""Pick the page sections most relevant to the search query (advanced enrichment).

Splits markdown into heading-aware chunks and ranks them with BM25. Only visible
text is scored (not URLs). Chunks never cross headings; gaps use an omission
marker and missing headings are restored on render. If ranking has nothing useful
to go on, returns the first ``budget`` characters of the page.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[^\W_]{2,}")
_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "all",
        "also",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "might",
        "more",
        "most",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "should",
        "so",
        "some",
        "than",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)
# URL artifacts: a query pasted as a company URL should reduce to the name itself
_URL_STOPWORDS = frozenset({"http", "https", "www", "com", "org", "net", "io"})
_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BARE_URL_RE = re.compile(r"<?https?://\S+>?")
_HEADING_RE = re.compile(r"^(#{1,6}) ")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_INVISIBLE = "​‌‍⁠﻿"
_INVISIBLE_NOISE_RE = re.compile(rf"(?:^|(?<=\s))[{_INVISIBLE}]+|[{_INVISIBLE}]+(?=\s|$)")
_TARGET_CHUNK_CHARS = 700
_MAX_CHUNK_CHARS = 1400
_MIN_TAIL_CHARS = 40  # stop filling once the leftover budget can't hold useful text
_MAX_SCAN_CHARS = 200_000  # bounds selection CPU only
_MAX_DF_RATIO = 0.5  # a term in more than half the chunks doesn't distinguish them
_BM25_K1 = 1.5
_BM25_B = 0.75
_PHRASE_BONUS = 1.5
_OWN_HEADING_BONUS = 1.0  # meaningful own-heading match
_NAV_PENALTY = 0.25  # demote link-dense nav blocks 
_NAV_MIN_LINKS = 3
_NAV_LABEL_RATIO = 0.6  # link-label share of visible tokens that marks a chunk as navigation
_MAX_DESCENDANT_SECTIONS = 3
_DESCENDANT_BUDGET_RATIO = 0.5  # page-budget share reserved for child-section leads under a matched heading
_ELISION = "[...]"
_JOIN = "\n\n"  
_ELISION_JOIN = f"\n\n{_ELISION}\n\n"  
_HEADING_SEP = "\n\n" 


@dataclass
class _Chunk:
    """One rankable unit of a page. Own heading and ancestors are scored separately, not folded together."""

    text: str
    heading: str  
    ancestors: tuple[str, ...] 
    section: int  
    piece: int  
    needs_prefix: bool  


def strip_invisible(text: str) -> str:
    """Remove stray invisible characters, then remove the extra blank lines they leave."""
    cleaned = _INVISIBLE_NOISE_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _visible_text(chunk: str) -> str:
    """Ranking input only: keep link labels, drop destinations and bare URLs."""
    return _BARE_URL_RE.sub(" ", _LINK_RE.sub(r"\1", chunk))


def _heading_level(block: str) -> int:
    match = _HEADING_RE.match(block)
    return len(match.group(1)) if match else 0


def _iter_blocks(text: str):
    """Blank-line-delimited blocks, splitting a heading off any body that shares its block."""
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if _heading_level(block) and "\n" in block:
            line, _, rest = block.partition("\n")
            yield line.strip()
            rest = rest.strip()
            if rest:
                yield rest
        else:
            yield block


def _split_oversized(unit: str) -> list[str]:
    """Split a unit over the max size on sentence boundaries; hard-slice sentences that never end."""
    if len(unit) <= _MAX_CHUNK_CHARS:
        return [unit]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_RE.split(unit):
        if not sentence:
            continue
        if len(sentence) > _MAX_CHUNK_CHARS:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(sentence[i : i + _MAX_CHUNK_CHARS] for i in range(0, len(sentence), _MAX_CHUNK_CHARS))
            continue
        if current and len(current) + 1 + len(sentence) > _TARGET_CHUNK_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        pieces.append(current)
    return pieces


def _merge_small(units: list[str]) -> list[str]:
    """Merge small body units up to the target size; callers pass one section's body only."""
    chunks: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + 2 + len(unit) > _TARGET_CHUNK_CHARS:
            chunks.append(current)
            current = unit
        else:
            current = f"{current}\n\n{unit}" if current else unit
    if current:
        chunks.append(current)
    return chunks


def _section_pieces(body: list[str]) -> list[str]:
    pieces = [piece for block in body for piece in _split_oversized(block)]
    return _merge_small(pieces)


def _chunk_markdown(text: str) -> list[_Chunk]:
    """Split the page into chunks in reading order.

    Each chunk remembers its heading and parent headings. Body text never
    crosses a heading, so different sections stay separate.
    """
    chunks: list[_Chunk] = []
    stack: list[tuple[int, str]] = []
    heading = ""
    ancestors: tuple[str, ...] = ()
    body: list[str] = []
    section = 0

    def flush() -> None:
        nonlocal body, section
        if any(block.strip() for block in body):
            for i, piece in enumerate(_section_pieces(body)):
                if heading and i == 0:
                    chunks.append(_Chunk(f"{heading}{_HEADING_SEP}{piece}", heading, ancestors, section, i, needs_prefix=False))
                elif heading:
                    chunks.append(_Chunk(piece, heading, ancestors, section, i, needs_prefix=True))
                else:
                    chunks.append(_Chunk(piece, "", (), section, i, needs_prefix=False))
            section += 1
        body = []

    for block in _iter_blocks(text):
        level = _heading_level(block)
        if level:
            flush()
            while stack and stack[-1][0] >= level:
                stack.pop()
            ancestors = tuple(line for _, line in stack)
            stack.append((level, block))
            heading = block
        else:
            body.append(block)
    flush()
    return chunks


def _bm25_scores(chunk_tokens: list[list[str]], query_tokens: set[str]) -> tuple[list[float], dict[str, int]]:
    """BM25 over token counts; returns per-chunk scores and per-term document frequency."""
    n = len(chunk_tokens)
    scores = [0.0] * n
    lengths = [len(tokens) for tokens in chunk_tokens]
    total = sum(lengths)
    if not total:
        return scores, {}
    avg_len = total / n
    counters = [Counter(tokens) for tokens in chunk_tokens]
    df = {term: sum(1 for counter in counters if term in counter) for term in query_tokens}
    for term, term_df in df.items():
        if not term_df:
            continue
        idf = math.log(1 + (n - term_df + 0.5) / (term_df + 0.5))
        for i, counter in enumerate(counters):
            tf = counter[term]
            if not tf:
                continue
            norm = _BM25_K1 * (1 - _BM25_B + _BM25_B * lengths[i] / avg_len)
            scores[i] += idf * tf * (_BM25_K1 + 1) / (tf + norm)
    return scores, df


def _strong_heading_match(heading_tokens: set[str], query_tokens: set[str], discriminative: set[str]) -> bool:
    """Whether a heading matches the query meaningfully, not just by sharing one ubiquitous word."""
    matched = query_tokens & heading_tokens
    if not matched:
        return False
    if len(query_tokens) == 1:  
        return True
    if not (matched & discriminative):  
        return False
    return len(matched) * 2 >= len(query_tokens) or len(matched) >= 2


def _is_nav_heavy(text: str) -> bool:
    """Whether a chunk is mostly link labels (a table of contents or nav list) rather than prose."""
    labels = _LINK_RE.findall(text)
    if len(labels) < _NAV_MIN_LINKS:
        return False
    label_tokens = sum(len(_tokenize(label)) for label in labels)
    visible = len(_tokenize(_visible_text(text)))
    return bool(visible) and label_tokens / visible >= _NAV_LABEL_RATIO


def _render(chunks: list[_Chunk], order: list[int], budget: int) -> str:
    parts: list[str] = []
    last_heading: str | None = None
    prev_idx: int | None = None
    for idx in order:
        chunk = chunks[idx]
        if parts:
            parts.append(_JOIN if idx == prev_idx + 1 else _ELISION_JOIN)
        if chunk.needs_prefix and chunk.heading != last_heading:
            parts.append(f"{chunk.heading}{_HEADING_SEP}")
        parts.append(chunk.text)
        last_heading = chunk.heading
        prev_idx = idx
    return "".join(parts)[:budget]


def select_relevant_content(markdown: str, query: str, budget: int) -> str:
    """Return the most query-relevant markdown within ``budget`` characters."""
    if budget <= 0:
        return ""
    text = strip_invisible(markdown).strip()
    if len(text) <= budget:
        return text
    ordered_terms = _tokenize(query)
    query_tokens = set(ordered_terms) - _STOPWORDS - _URL_STOPWORDS
    if not query_tokens:
        return text[:budget]

    chunks = _chunk_markdown(text[:_MAX_SCAN_CHARS])
    if not chunks:
        return text[:budget]
    n = len(chunks)
    body_tokens = [_tokenize(_visible_text(chunk.text)) for chunk in chunks]
    own_heading_sets = [set(_tokenize(_visible_text(chunk.heading))) for chunk in chunks]
    ancestor_sets = [set(_tokenize(_visible_text("\n".join(chunk.ancestors)))) for chunk in chunks]
    bag = [body_tokens[i] + (list(own_heading_sets[i]) if chunks[i].needs_prefix else []) for i in range(n)]
    scores, df = _bm25_scores(bag, query_tokens)

    discriminative = {term for term, count in df.items() if count and count / n <= _MAX_DF_RATIO}
    phrase = " ".join(ordered_terms) if len(ordered_terms) >= 2 else ""
    has_signal = [False] * n
    own_strong = [False] * n
    for i in range(n):
        phrase_hit = bool(phrase) and f" {phrase} " in f" {' '.join(body_tokens[i])} "
        own_strong[i] = _strong_heading_match(own_heading_sets[i], query_tokens, discriminative)
        ancestor_strong = _strong_heading_match(ancestor_sets[i], query_tokens, discriminative)
        if phrase_hit:
            scores[i] += _PHRASE_BONUS
        if own_strong[i]:
            scores[i] += _OWN_HEADING_BONUS
        if _is_nav_heavy(chunks[i].text):
            scores[i] *= _NAV_PENALTY
        lead_inherits = chunks[i].piece == 0 and ancestor_strong
        has_signal[i] = phrase_hit or own_strong[i] or bool(discriminative & set(bag[i])) or lead_inherits
    if not any(has_signal):
        return text[:budget]

    section_leads: dict[int, int] = {}
    for i in range(n):
        section_leads.setdefault(chunks[i].section, i)  # first chunk seen for a section is its lead

    selected: list[int] = []
    chosen: set[int] = set()
    seen: set[str] = set()
    remaining = budget

    def _consider(order: list[int], cap: int, allow_truncate: bool) -> str | None:
        nonlocal remaining
        for i in order:
            if i in chosen:
                continue
            normalized = " ".join(chunks[i].text.split()).lower()  # dedupes exact repetition only
            if normalized in seen:
                continue
            prefix_cost = len(chunks[i].heading) + len(_HEADING_SEP) if chunks[i].needs_prefix else 0
            cost = len(chunks[i].text) + prefix_cost + (len(_ELISION_JOIN) if selected else 0)
            if cost <= min(cap, remaining):
                selected.append(i)
                chosen.add(i)
                seen.add(normalized)
                remaining -= cost
            elif allow_truncate and not selected:
                return chunks[i].text[:budget] 
            if remaining < _MIN_TAIL_CHARS:
                break
        return None

    ranked = sorted((i for i in range(n) if has_signal[i] and scores[i] > 0), key=lambda i: (-scores[i], i))

    # When a heading strongly matches the query, keep some budget for the first
    # chunks of its child sections
    anchor: int | None = None
    best_key: tuple[float, int] | None = None
    for sid, lead in section_leads.items():
        if not own_strong[lead]:
            continue
        key = (scores[lead], _heading_level(chunks[lead].heading))  # strongest score, deepest heading on ties
        if best_key is None or key > best_key:
            best_key, anchor = key, sid
    if anchor is not None:
        anchor_heading = chunks[section_leads[anchor]].heading
        descendants = [
            lead
            for sid, lead in section_leads.items()
            if sid != anchor and anchor_heading in chunks[lead].ancestors
        ]
        descendants.sort(key=lambda i: (-scores[i], i))  
        reserved = int(budget * _DESCENDANT_BUDGET_RATIO)
        _consider(descendants[:_MAX_DESCENDANT_SECTIONS], reserved, allow_truncate=False)

    best_in_section: dict[int, int] = {}
    for i in ranked:
        best_in_section.setdefault(chunks[i].section, i)
    stage1 = [i for i in ranked if best_in_section[chunks[i].section] == i]
    stage2 = [i for i in ranked if best_in_section[chunks[i].section] != i]
    truncated = _consider(stage1, budget, allow_truncate=True)
    if truncated is not None:
        return truncated
    _consider(stage2, budget, allow_truncate=False)

    if not selected:
        return text[:budget]
    return _render(chunks, sorted(selected), budget)
