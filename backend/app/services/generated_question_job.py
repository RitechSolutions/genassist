"""Fills a dataset with test questions written from a knowledge base."""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Set, Tuple
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage

from app.modules.data.providers.models import StoredDocument
from app.schemas.test_suite import TestCaseCreate
from app.services import generated_question_runs as runs
from app.services.generated_questions import (
    GENERATED_TAG,
    MESSAGES_PER_ARTICLE,
    SEARCH_LIMIT,
    ArticleOutcome,
    Ask,
    QuestionWriter,
    Search,
)

logger = logging.getLogger(__name__)

CONCURRENT_ARTICLES = 4
TIME_LIMIT_SECONDS = 2 * 60 * 60
# No new article is started this long before the limit, so the ones in progress can finish.
STOP_MARGIN_SECONDS = 5 * 60
NO_ARTICLES_ERROR = "This knowledge base has no stored articles to read."
NOTHING_ANSWERED_ERROR = "The model or the knowledge search did not answer for the first articles."
TIME_LIMIT_ERROR = "Stopped at the time limit; the questions written so far were added."
RUN_FAILED_ERROR = "The run failed."


@dataclass(frozen=True)
class QuestionRunRequest:
    tenant_id: str
    suite_id: UUID
    knowledge_base_id: UUID
    llm_provider_id: UUID
    run_id: str
    sample_size: Optional[int] = None


@dataclass
class Counts:
    articles_total: int = 0
    articles_done: int = 0
    articles_failed: int = 0
    messages_added: int = 0
    messages_dropped: int = 0


def model_calls(article_count: int, sample_size: Optional[int] = None) -> Dict[str, int]:
    """What a run would ask of the model: one writing call per article, and the most judging calls it can need."""
    articles = min(article_count, sample_size) if sample_size else article_count
    return {
        "articles": articles,
        "writing_calls": articles,
        "judging_calls_at_most": articles * MESSAGES_PER_ARTICLE * SEARCH_LIMIT,
    }


def reply_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") for block in content if isinstance(block, dict))


def sampled(documents: Sequence[StoredDocument], sample_size: Optional[int]) -> List[StoredDocument]:
    if sample_size and sample_size < len(documents):
        return random.sample(list(documents), sample_size)
    return list(documents)


def _batches(items: Sequence[Any], size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _same_message(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


class GeneratedQuestionJob:
    """One run: reads the articles, has the messages written and checked, and adds the kept ones as turns."""

    def __init__(
        self, suite_service, knowledge_service, rag_manager, llm_provider, run_store,
        commit: Callable[[], Awaitable[None]],
    ):
        self._suites = suite_service
        self._knowledge = knowledge_service
        self._rag = rag_manager
        self._llm = llm_provider
        self._runs = run_store
        # Saves what the run has added so far, so a long run keeps its progress.
        self._commit = commit

    async def run(self, request: QuestionRunRequest) -> None:
        """Fill the dataset and record how the run ended, also when the worker's time limit cuts it off."""
        deadline = time.monotonic() + TIME_LIMIT_SECONDS - STOP_MARGIN_SECONDS
        counts = Counts()
        try:
            status, error = await self._fill(request, counts, deadline)
        except asyncio.CancelledError:
            await self._finish(request, counts, runs.STATUS_STOPPED, TIME_LIMIT_ERROR)
            raise
        except Exception:
            logger.exception("Question run %s failed", request.run_id)
            status, error = runs.STATUS_FAILED, RUN_FAILED_ERROR
        await self._finish(request, counts, status, error)

    async def _fill(self, request: QuestionRunRequest, counts: Counts, deadline: float) -> Tuple[str, Optional[str]]:
        """Run the articles in batches; returns how the run ended and why."""
        if not await self._report(request, counts):
            return runs.STATUS_FAILED, runs.RUN_LOST_ERROR
        knowledge_base = await self._knowledge.get_by_id(request.knowledge_base_id)
        documents = await self._rag.get_documents(knowledge_base)
        if not documents:
            return runs.STATUS_FAILED, NO_ARTICLES_ERROR
        writer = QuestionWriter(await self._ask(request.llm_provider_id), self._search(knowledge_base), documents)
        chosen = sampled(documents, request.sample_size)
        counts.articles_total = len(chosen)
        known = await self._known_messages(request.suite_id)
        await self._commit()
        for batch in _batches(chosen, CONCURRENT_ARTICLES):
            if time.monotonic() >= deadline:
                return runs.STATUS_STOPPED, TIME_LIMIT_ERROR
            if not await self._report(request, counts):
                return runs.STATUS_FAILED, runs.RUN_LOST_ERROR
            outcomes = await asyncio.gather(*(self._written(writer, document) for document in batch))
            if not await self._runs.holds(request.tenant_id, str(request.suite_id), request.run_id):
                return runs.STATUS_FAILED, runs.RUN_LOST_ERROR
            added = 0
            for outcome in outcomes:
                added += await self._save(request.suite_id, outcome, known, counts)
            await self._commit()
            counts.messages_added += added
            nothing_answered = counts.articles_done == 0
            if nothing_answered:
                return runs.STATUS_FAILED, NOTHING_ANSWERED_ERROR
        return runs.STATUS_SUCCEEDED, None

    async def _ask(self, llm_provider_id: UUID) -> Ask:
        model = await self._llm.get_model(str(llm_provider_id))

        async def ask(system: str, human: str) -> str:
            response = await model.ainvoke([SystemMessage(content=system), HumanMessage(content=human)])
            return reply_text(response)

        return ask

    def _search(self, knowledge_base) -> Search:
        async def search(query: str):
            return await self._rag.search([knowledge_base], query, limit=SEARCH_LIMIT)

        return search

    async def _written(self, writer: QuestionWriter, document: StoredDocument) -> Optional[ArticleOutcome]:
        """The article's outcome; None when writing or checking it failed, so one article cannot end the run."""
        try:
            return await writer.messages_for(document)
        except Exception:
            logger.exception("Could not write questions for document %s", document.id)
            return None

    async def _save(self, suite_id: UUID, outcome: Optional[ArticleOutcome], known: Set[str], counts: Counts) -> int:
        """Add the article's kept messages that the dataset does not hold yet; returns how many were added."""
        if outcome is None:
            counts.articles_failed += 1
            return 0
        added = 0
        counts.articles_done += 1
        counts.messages_dropped += outcome.dropped
        for generated in outcome.kept:
            is_duplicate = _same_message(generated.message) in known
            if is_duplicate:
                counts.messages_dropped += 1
                continue
            await self._suites.add_case(TestCaseCreate(
                suite_id=suite_id,
                input_data={"message": generated.message},
                expected_articles=generated.expected_articles,
                tags=[GENERATED_TAG],
                source_conversation_id=uuid.uuid4(),
                turn_index=0,
            ))
            known.add(_same_message(generated.message))
            added += 1
        return added

    async def _known_messages(self, suite_id: UUID) -> Set[str]:
        cases = await self._suites.list_cases_for_suite(suite_id)
        return {_same_message((case.input_data or {}).get("message")) for case in cases}

    async def _report(self, request: QuestionRunRequest, counts: Counts) -> bool:
        return await self._runs.report(request.tenant_id, str(request.suite_id), request.run_id, asdict(counts))

    async def _finish(self, request: QuestionRunRequest, counts: Counts, status: str, error: Optional[str]) -> None:
        await self._runs.finish(request.tenant_id, str(request.suite_id), request.run_id, status, error, asdict(counts))
