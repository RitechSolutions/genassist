"""Test questions are written from an article and kept only when their expected article holds up."""
import json
from types import SimpleNamespace

import pytest

from app.modules.data.providers.models import StoredDocument
from app.services.generated_questions import (
    JUDGE_PROMPT,
    WRITE_PROMPT,
    GeneratedMessage,
    QuestionWriter,
    copies_article,
    expected_names,
    parsed_messages,
    ranked_above,
    source_goes_first,
    verdict_of,
)

LOCK = StoredDocument(
    id="KB:kb-1#article_1", title="Lock the bike",
    content="Lock the bike\nPush the ring lock on the back wheel down until it clicks.",
)
RETURN = StoredDocument(
    id="KB:kb-1#article_2", title="Return the bike",
    content="Return the bike\nPark it at any station and wait for the green light on the dock.",
)
MESSAGE = "My bike rolled away outside the shop, how do I stop that?"


def written(*messages):
    return json.dumps({"messages": list(messages)})


def result(document):
    return SimpleNamespace(id=document.id)


class Model:
    """Answers the writing prompt with fixed messages and the judge with a fixed pick."""

    def __init__(self, messages, pick="SOURCE"):
        self.messages = messages
        self.pick = pick
        self.judged = []

    async def ask(self, system, human):
        if system == WRITE_PROMPT:
            return written(*self.messages)
        assert system == JUDGE_PROMPT
        self.judged.append(human)
        if self.pick in ("BOTH", "NEITHER", "no idea"):
            return f"ANSWERS: {self.pick}"
        source_is_first = human.index(LOCK.content) < human.index(RETURN.content)
        picks_first = (self.pick == "SOURCE") == source_is_first
        return f"ANSWERS: {1 if picks_first else 2}"


def writer(model, *found):
    searched = []

    async def search(query):
        searched.append(query)
        return [result(document) for document in found]

    built = QuestionWriter(model.ask, search, [LOCK, RETURN])
    built.searched = searched
    return built


class TestReply:
    def test_the_messages_are_read_from_the_json_in_the_reply(self):
        assert parsed_messages('Here you go: {"messages": ["  First ", "Second", "Third"]}') == ["First", "Second"]

    @pytest.mark.parametrize("reply", ["no json here", '{"messages": "one text"}', '{"other": []}', "", '{"messages": [1, null]}'])
    def test_a_reply_in_another_form_gives_no_messages(self, reply):
        assert parsed_messages(reply) == []


class TestCopying:
    def test_four_words_in_a_row_from_the_article_count_as_copied(self):
        assert copies_article("Should I push the ring lock on it?", LOCK)

    def test_a_long_title_found_whole_counts_as_repeated(self):
        assert copies_article("How do I lock the bike?", LOCK)

    def test_a_message_in_its_own_words_is_not_copied(self):
        assert not copies_article(MESSAGE, LOCK)

    def test_a_short_title_may_appear_in_a_message(self):
        short = StoredDocument(id="doc", title="Refunds", content="Refunds\nMoney comes back in five days.")
        assert not copies_article("When do refunds arrive?", short)


class TestExpectedName:
    def test_a_title_no_other_document_has_is_the_name(self):
        assert expected_names([LOCK, RETURN]) == {LOCK.id: "Lock the bike", RETURN.id: "Return the bike"}

    def test_documents_sharing_a_title_are_named_by_their_id_without_the_knowledge_base(self):
        twin = StoredDocument(id="KB:kb-1#manual.pdf", title=" lock  the BIKE", content="Other text")
        untitled = StoredDocument(id="KB:kb-1#notes.txt", title=None, content="Notes")
        assert expected_names([LOCK, twin, untitled]) == {
            LOCK.id: "article_1", twin.id: "manual.pdf", untitled.id: "notes.txt",
        }


class TestRanking:
    def test_only_documents_above_the_source_are_compared(self):
        assert ranked_above("b", ["a", "a", "b", "c"]) == ["a"]

    def test_every_result_is_compared_when_the_source_is_missing(self):
        assert ranked_above("z", ["a", "b"]) == ["a", "b"]


class TestVerdict:
    def test_the_number_is_read_in_the_order_the_judge_saw_the_articles(self):
        assert verdict_of("ANSWERS: 1", source_first=True) == "SOURCE"
        assert verdict_of("answers : 1", source_first=False) == "OTHER"
        assert verdict_of("ANSWERS: 2", source_first=False) == "SOURCE"

    def test_both_neither_and_an_unreadable_reply(self):
        assert verdict_of("ANSWERS: BOTH", True) == "BOTH"
        assert verdict_of("ANSWERS: NEITHER", True) == "NEITHER"
        assert verdict_of("I think the first one", True) == "UNCLEAR"

    def test_the_order_is_fixed_for_a_pair(self):
        assert source_goes_first(MESSAGE, RETURN.id) == source_goes_first(MESSAGE, RETURN.id)


class TestWriter:
    @pytest.mark.asyncio
    async def test_a_message_whose_article_is_found_first_is_kept_without_a_judge(self):
        model = Model([MESSAGE])
        outcome = await writer(model, LOCK, RETURN).messages_for(LOCK)
        assert outcome.kept == [GeneratedMessage(MESSAGE, ["Lock the bike"])]
        assert outcome.dropped == 0 and model.judged == []

    @pytest.mark.asyncio
    async def test_the_judge_confirming_the_source_keeps_the_message(self):
        model = Model([MESSAGE], pick="SOURCE")
        outcome = await writer(model, RETURN, LOCK).messages_for(LOCK)
        assert outcome.kept == [GeneratedMessage(MESSAGE, ["Lock the bike"])]
        assert len(model.judged) == 1

    @pytest.mark.asyncio
    async def test_both_articles_answering_adds_the_other_one(self):
        outcome = await writer(Model([MESSAGE], pick="BOTH"), RETURN, LOCK).messages_for(LOCK)
        assert outcome.kept == [GeneratedMessage(MESSAGE, ["Lock the bike", "Return the bike"])]

    @pytest.mark.parametrize("pick", ["OTHER", "NEITHER", "no idea"])
    @pytest.mark.asyncio
    async def test_a_message_the_judge_does_not_confirm_is_dropped(self, pick):
        outcome = await writer(Model([MESSAGE], pick=pick), RETURN).messages_for(LOCK)
        assert outcome.kept == [] and outcome.dropped == 1

    @pytest.mark.asyncio
    async def test_a_copied_message_is_dropped_before_any_search(self):
        built = writer(Model(["How do I lock the bike?", MESSAGE]), LOCK)
        outcome = await built.messages_for(LOCK)
        assert [kept.message for kept in outcome.kept] == [MESSAGE]
        assert outcome.dropped == 1 and built.searched == [MESSAGE]

    @pytest.mark.asyncio
    async def test_a_result_that_is_not_a_stored_document_is_not_compared(self):
        unknown = StoredDocument(id="KB:kb-9#gone", title="Gone", content="Gone")
        model = Model([MESSAGE])
        outcome = await writer(model, unknown, LOCK).messages_for(LOCK)
        assert outcome.kept == [GeneratedMessage(MESSAGE, ["Lock the bike"])] and model.judged == []
