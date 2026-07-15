"""Pick the parts of a page most relevant to the search query (advanced enrichment).

Splits page markdown into chunks (each section kept with its heading) and ranks
them against the query with a small BM25 scorer built. Only visible
text is scored: link URLs and bare URLs are ignored, so a query that includes a
company URL can't be gamed by pages that repeat that URL in hrefs. If the query
gives nothing useful to rank on (no tokens, no matches, or every chunk looks the
same — and no exact phrase or heading match), the caller gets the first ``budget`` characters of the page.
"""

import math
import re
from collections import Counter

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
_HEADING_RE = re.compile(r"#{1,6} ")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_TARGET_CHUNK_CHARS = 700
_MAX_CHUNK_CHARS = 1400
_MIN_TAIL_CHARS = 40  # stop filling once the leftover budget can't hold useful text
_MAX_SCAN_CHARS = 200_000  # bounds selection CPU only
_MAX_DF_RATIO = 0.5  # a term in more than half the chunks doesn't distinguish them
_BM25_K1 = 1.5
_BM25_B = 0.75
_PHRASE_BONUS = 1.5
_HEADING_BONUS = 0.5


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _visible_text(chunk: str) -> str:
    """Ranking input only: keep link labels, drop destinations and bare URLs."""
    return _BARE_URL_RE.sub(" ", _LINK_RE.sub(r"\1", chunk))


def _heading_tokens(chunk: str) -> set[str]:
    lines = [line for line in chunk.split("\n") if _HEADING_RE.match(line)]
    return set(_tokenize(" ".join(lines))) if lines else set()


def _glue_headings(blocks: list[str]) -> list[str]:
    """Attach heading-only blocks to the following body block so headings never stand alone."""
    units: list[str] = []
    pending: list[str] = []
    for block in blocks:
        if _HEADING_RE.match(block) and "\n" not in block:
            pending.append(block)
            continue
        if pending:
            block = "\n\n".join((*pending, block))
            pending = []
        units.append(block)
    if pending:
        units.append("\n\n".join(pending))
    return units


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


def _chunk_markdown(text: str) -> list[str]:
    """Document-order chunks: glue headings, split oversized units, merge small ones."""
    blocks = [block for block in text.split("\n\n") if block.strip()]
    units = _glue_headings(blocks)
    pieces = [piece for unit in units for piece in _split_oversized(unit)]
    return _merge_small(pieces)


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


def select_relevant_content(markdown: str, query: str, budget: int) -> str:
    """Return the most query-relevant markdown within ``budget`` characters."""
    if budget <= 0:
        return ""
    text = markdown.strip()
    if len(text) <= budget:
        return text
    ordered_terms = _tokenize(query)
    query_tokens = set(ordered_terms) - _STOPWORDS - _URL_STOPWORDS
    if not query_tokens:
        return text[:budget]

    chunks = _chunk_markdown(text[:_MAX_SCAN_CHARS])
    chunk_tokens = [_tokenize(_visible_text(chunk)) for chunk in chunks]
    scores, df = _bm25_scores(chunk_tokens, query_tokens)

    n = len(chunks)
    discriminative = {term for term, count in df.items() if count and count / n <= _MAX_DF_RATIO}
    phrase = " ".join(ordered_terms) if len(ordered_terms) >= 2 else ""
    has_signal = [False] * n
    for i, tokens in enumerate(chunk_tokens):
        phrase_hit = bool(phrase) and f" {phrase} " in f" {' '.join(tokens)} "
        heading_hit = bool(query_tokens & _heading_tokens(chunks[i]))
        if phrase_hit:
            scores[i] += _PHRASE_BONUS
        if heading_hit:
            scores[i] += _HEADING_BONUS
        has_signal[i] = phrase_hit or heading_hit or bool(discriminative & set(tokens))
    if not any(has_signal):
        return text[:budget]

    ranked = sorted((i for i in range(n) if has_signal[i] and scores[i] > 0), key=lambda i: (-scores[i], i))
    selected: list[int] = []
    seen: set[str] = set()
    remaining = budget
    for i in ranked:
        normalized = " ".join(chunks[i].split()).lower()  # dedupes exact repetition only
        if normalized in seen:
            continue
        cost = len(chunks[i]) + (2 if selected else 0)
        if cost <= remaining:
            selected.append(i)
            seen.add(normalized)
            remaining -= cost
        elif not selected:
            # the single best chunk overflows: its head beats a weaker whole chunk
            return chunks[i][:budget]
        if remaining < _MIN_TAIL_CHARS:
            break
    if not selected:
        return text[:budget]
    return "\n\n".join(chunks[i] for i in sorted(selected))
