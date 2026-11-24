"""Test questions written from a knowledge base's articles, each with the article it should find.

Pure of the database and of any model client: the caller passes how to ask the model and how to search.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from app.modules.data.providers.models import SearchResult, StoredDocument

MESSAGES_PER_ARTICLE = 2
# The most of an article the model reads.
ARTICLE_CHARACTERS = 8000
SEARCH_LIMIT = 5
COPIED_WORDS_IN_A_ROW = 4
# A title this long, found whole in a message, counts as repeated.
REPEATED_TITLE_WORDS = 3
GENERATED_TAG = "generated"

SOURCE = "SOURCE"
OTHER = "OTHER"
BOTH = "BOTH"
NEITHER = "NEITHER"
UNCLEAR = "UNCLEAR"

WRITE_PROMPT = (
    "You write test messages for a customer support chat.\n"
    f"You get one help article. Write {MESSAGES_PER_ARTICLE} messages that a real customer could type into "
    "the support chat and that this article answers.\n"
    "Rules:\n"
    "- Write as the customer, in everyday words. The customer has never seen the article and does not use "
    "its title, its headings or its special terms.\n"
    "- Each message is one or two informal sentences describing a concrete situation or problem, the way "
    "people write when something went wrong. It does not have to be a question.\n"
    "- The messages are about different situations.\n"
    "- The article must contain what is needed to answer each message.\n"
    "- Never copy four or more words in a row from the article.\n"
    "- Write in the language of the article.\n"
    'Reply with JSON only: {"messages": ["...", "..."]}'
)
JUDGE_PROMPT = (
    "You check which help article answers a customer's message.\n"
    "You get one customer message and two help articles.\n"
    "An article answers the message when it contains the information a support agent needs to resolve "
    "this exact message. An article that only mentions the topic, or only sends the reader to another "
    "article or to customer support, does not answer it.\n"
    "Reply with exactly one line and nothing else:\n"
    "ANSWERS: 1, 2, BOTH or NEITHER"
)

Ask = Callable[[str, str], Awaitable[str]]
Search = Callable[[str], Awaitable[Sequence[SearchResult]]]


@dataclass(frozen=True)
class GeneratedMessage:
    message: str
    expected_articles: List[str]


@dataclass
class ArticleOutcome:
    """What one article gave: the messages to add, and how many were written but not kept."""

    kept: List[GeneratedMessage] = field(default_factory=list)
    dropped: int = 0


def article_text(document: StoredDocument) -> str:
    return document.content[:ARTICLE_CHARACTERS]


def parsed_messages(reply: str) -> List[str]:
    """The messages in a model reply; none when the reply is not the JSON asked for."""
    found = re.search(r"\{.*\}", reply or "", flags=re.DOTALL)
    if not found:
        return []
    try:
        messages = json.loads(found.group(0)).get("messages", [])
    except (json.JSONDecodeError, AttributeError):
        return []
    if not isinstance(messages, list):
        return []
    texts = [str(message).strip() for message in messages if isinstance(message, str)]
    return [text for text in texts if text][:MESSAGES_PER_ARTICLE]


def _words(text: str) -> List[str]:
    return re.findall(r"\w+", (text or "").lower())


def _runs(words: Sequence[str], length: int) -> set:
    return {tuple(words[start:start + length]) for start in range(len(words) - length + 1)}


def copies_article(message: str, document: StoredDocument) -> bool:
    """True when the message repeats the article's title or copies words in a row from it."""
    message_words = _words(message)
    title_words = _words(document.title or "")
    is_long_title = len(title_words) >= REPEATED_TITLE_WORDS
    repeats_title = is_long_title and tuple(title_words) in _runs(message_words, len(title_words))
    copied_runs = _runs(message_words, COPIED_WORDS_IN_A_ROW) & _runs(_words(document.content), COPIED_WORDS_IN_A_ROW)
    return repeats_title or bool(copied_runs)


def _same_title(title: str) -> str:
    return " ".join(title.lower().split())


def portable_id(document_id: str) -> str:
    """The id without its knowledge-base part, which differs between environments."""
    return document_id.split("#", 1)[-1]


def expected_names(documents: Sequence[StoredDocument]) -> Dict[str, str]:
    """How each document is written as an expected article: its title when no other shares it, else its id."""
    shared = Counter(_same_title(document.title) for document in documents if document.title)
    names = {}
    for document in documents:
        has_own_title = bool(document.title) and shared[_same_title(document.title)] == 1
        names[document.id] = document.title if has_own_title else portable_id(document.id)
    return names


def ranked_above(source_id: str, result_ids: Sequence[str]) -> List[str]:
    """The documents the search put above the source one; every result when the source is not among them."""
    ordered = list(dict.fromkeys(result_ids))
    if source_id in ordered:
        return ordered[: ordered.index(source_id)]
    return ordered


def source_goes_first(message: str, other_id: str) -> bool:
    """Which article the judge reads first, fixed per pair so the order cannot favour the source."""
    digest = hashlib.sha256(f"{message}\n{other_id}".encode("utf-8")).digest()
    return digest[0] % 2 == 0


def judge_request(message: str, source: StoredDocument, other: StoredDocument) -> Tuple[str, bool]:
    source_first = source_goes_first(message, other.id)
    first, second = (source, other) if source_first else (other, source)
    text = f"Customer message: {message}\n\nArticle 1:\n{article_text(first)}\n\nArticle 2:\n{article_text(second)}"
    return text, source_first


def verdict_of(reply: str, source_first: bool) -> str:
    """Which article the judge says answers the message; UNCLEAR when the reply is not in the asked form."""
    found = re.search(r"ANSWERS\s*:\s*(BOTH|NEITHER|1|2)", reply or "", flags=re.IGNORECASE)
    if not found:
        return UNCLEAR
    answer = found.group(1).upper()
    if answer in (BOTH, NEITHER):
        return answer
    return SOURCE if (answer == "1") == source_first else OTHER


class QuestionWriter:
    """Writes test messages for an article and keeps those whose expected article holds up."""

    def __init__(self, ask: Ask, search: Search, documents: Sequence[StoredDocument]):
        self._ask = ask
        self._search = search
        self._documents = {document.id: document for document in documents}
        self._names = expected_names(documents)

    async def messages_for(self, document: StoredDocument) -> ArticleOutcome:
        reply = await self._ask(WRITE_PROMPT, f"Help article:\n{article_text(document)}")
        outcome = ArticleOutcome()
        for message in parsed_messages(reply):
            kept = None if copies_article(message, document) else await self._confirmed(message, document)
            if kept is None:
                outcome.dropped += 1
            else:
                outcome.kept.append(kept)
        return outcome

    async def _confirmed(self, message: str, source: StoredDocument) -> Optional[GeneratedMessage]:
        """The message with its expected articles; None when the judge does not confirm the source article."""
        results = await self._search(message)
        expected = [self._names[source.id]]
        for other_id in ranked_above(source.id, [result.id for result in results]):
            other = self._documents.get(other_id)
            if other is None:
                continue
            verdict = await self._verdict(message, source, other)
            if verdict == BOTH:
                expected.append(self._names[other.id])
            elif verdict != SOURCE:
                return None
        return GeneratedMessage(message, expected)

    async def _verdict(self, message: str, source: StoredDocument, other: StoredDocument) -> str:
        text, source_first = judge_request(message, source, other)
        return verdict_of(await self._ask(JUDGE_PROMPT, text), source_first)
