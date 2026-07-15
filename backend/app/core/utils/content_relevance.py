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
_HEADING_BONUS = 0.5
_ELISION = "[...]"
_JOIN = "\n\n"  
_ELISION_JOIN = f"\n\n{_ELISION}\n\n"  
_HEADING_SEP = "\n\n" 


@dataclass
class _Chunk:
    """One rankable unit of a page. ``context`` (heading + ancestors) is scored but not part of ``text``."""

    text: str
    heading: str  # nearest heading line, "" for pre-heading content
    context: str  # heading + open ancestor headings, for scoring only
    needs_prefix: bool  # text lost its heading and should get it re-prepended on render


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
    ancestors: list[str] = []
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        if any(block.strip() for block in body):
            context = "\n".join([heading, *ancestors]).strip()
            for i, piece in enumerate(_section_pieces(body)):
                if heading and i == 0:
                    chunks.append(_Chunk(f"{heading}{_HEADING_SEP}{piece}", heading, context, needs_prefix=False))
                elif heading:
                    chunks.append(_Chunk(piece, heading, context, needs_prefix=True))
                else:
                    chunks.append(_Chunk(piece, "", "", needs_prefix=False))
        body = []

    for block in _iter_blocks(text):
        level = _heading_level(block)
        if level:
            flush()
            while stack and stack[-1][0] >= level:
                stack.pop()
            ancestors = [line for _, line in stack]
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
    body_tokens = [_tokenize(_visible_text(chunk.text)) for chunk in chunks]
    context_sets = [set(_tokenize(_visible_text(chunk.context))) for chunk in chunks]
    chunk_tokens = [tokens + list(context) for tokens, context in zip(body_tokens, context_sets)]
    scores, df = _bm25_scores(chunk_tokens, query_tokens)

    n = len(chunks)
    discriminative = {term for term, count in df.items() if count and count / n <= _MAX_DF_RATIO}
    phrase = " ".join(ordered_terms) if len(ordered_terms) >= 2 else ""
    has_signal = [False] * n
    for i in range(n):
        phrase_hit = bool(phrase) and f" {phrase} " in f" {' '.join(body_tokens[i])} "
        heading_hit = bool(query_tokens & context_sets[i])
        if phrase_hit:
            scores[i] += _PHRASE_BONUS
        if heading_hit:
            scores[i] += _HEADING_BONUS
        has_signal[i] = phrase_hit or heading_hit or bool(discriminative & set(chunk_tokens[i]))
    if not any(has_signal):
        return text[:budget]

    ranked = sorted((i for i in range(n) if has_signal[i] and scores[i] > 0), key=lambda i: (-scores[i], i))
    selected: list[int] = []
    seen: set[str] = set()
    remaining = budget
    for i in ranked:
        normalized = " ".join(chunks[i].text.split()).lower()  # dedupes exact repetition only
        if normalized in seen:
            continue
        prefix_cost = len(chunks[i].heading) + len(_HEADING_SEP) if chunks[i].needs_prefix else 0
        cost = len(chunks[i].text) + prefix_cost + (len(_ELISION_JOIN) if selected else 0)
        if cost <= remaining:
            selected.append(i)
            seen.add(normalized)
            remaining -= cost
        elif not selected:
            return chunks[i].text[:budget]
        if remaining < _MIN_TAIL_CHARS:
            break
    if not selected:
        return text[:budget]
    return _render(chunks, sorted(selected), budget)
