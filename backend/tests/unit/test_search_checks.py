"""What a turn's knowledge searches found, and whether an article is among it."""
from types import SimpleNamespace

from app.services.search_checks import (
    MAX_LISTED_ARTICLES,
    NO_ARTICLES,
    NO_SEARCH,
    SEARCH_FAILED,
    article_fact,
    knowledge_searches,
    within_first_phrase,
)
from app.services.test_suite import turn_record

KB = "KB:11111111-1111-1111-1111-111111111111"


def source(article_id, title, score=0.5):
    return {"id": f"{KB}#{article_id}", "title": title, "score": score, "source": "vector", "kb_id": "kb-1"}


def search_run(*sources, start=0, status="success", error=None, name="Help centre"):
    run = {"type": "knowledgeBaseNode", "name": name, "status": status, "startTime": start, "error": error}
    if status == "success":
        run["sources"] = list(sources)
    return run


def search(*articles, failed=False):
    return {"step": "kb", "label": "Help centre", "failed": failed, "articles": list(articles)}


def article(article_id, title):
    return {"id": f"{KB}#{article_id}", "title": title, "score": 0.5}


class TestKnowledgeSearches:
    def test_searches_are_listed_in_the_order_they_ran(self):
        status = {
            "kb": search_run(source("article_3", "Pay for a ride"), start=30),
            "kb_0": search_run(source("article_1", "Lock the bike"), start=10),
            "kb_1": search_run(source("article_2", "Return the bike"), start=20),
        }

        searches = knowledge_searches(status)

        assert [found["step"] for found in searches] == ["kb_0", "kb_1", "kb"]
        assert [found["articles"][0]["title"] for found in searches] == [
            "Lock the bike", "Return the bike", "Pay for a ride",
        ]

    def test_articles_keep_the_order_the_search_returned(self):
        status = {"kb": search_run(source("article_1", "Lock the bike", 0.9), source("article_2", "Return the bike", 0.4))}

        (found,) = knowledge_searches(status)

        assert found["articles"] == [
            {"id": f"{KB}#article_1", "title": "Lock the bike", "score": 0.9},
            {"id": f"{KB}#article_2", "title": "Return the bike", "score": 0.4},
        ]
        assert found["label"] == "Help centre"

    def test_only_knowledge_search_steps_count(self):
        status = {
            "agent": {"type": "agentNode", "status": "success", "sources": [source("article_1", "Lock the bike")]},
            "kb": search_run(source("article_1", "Lock the bike")),
            "broken": "not a step",
        }

        assert [found["step"] for found in knowledge_searches(status)] == ["kb"]

    def test_a_failed_search_is_listed_without_articles(self):
        (found,) = knowledge_searches({"kb": search_run(status="failed", error="timed out")})

        assert found["failed"] is True
        assert found["articles"] == []

    def test_a_run_without_steps_has_no_searches(self):
        assert knowledge_searches({}) == []
        assert knowledge_searches(None) == []


class TestArticleFact:
    def test_an_article_is_found_by_its_title_whatever_the_case_or_spacing(self):
        searches = [search(article("article_1", "Lock the bike"))]

        assert article_fact(["  lock  the BIKE "], searches) == (
            True, 'The knowledge search found "Lock the bike" as result 1.',
        )

    def test_an_article_is_found_by_its_id_with_or_without_the_knowledge_base_part(self):
        searches = [search(article("article_1", "Lock the bike"))]

        assert article_fact([f"{KB}#article_1"], searches)[0] is True
        assert article_fact(["article_1"], searches)[0] is True
        assert article_fact(["article_10"], searches)[0] is False

    def test_any_of_the_wanted_articles_counts(self):
        searches = [search(article("article_1", "Lock the bike"), article("article_2", "Return the bike"))]

        assert article_fact(["Unlock the bike", "Return the bike"], searches) == (
            True, 'The knowledge search found "Return the bike" as result 2.',
        )

    def test_the_best_position_over_every_search_counts(self):
        searches = [
            search(article("article_1", "Lock the bike"), article("article_2", "Return the bike")),
            search(article("article_2", "Return the bike")),
        ]

        assert article_fact(["Return the bike"], searches, within_first=1) == (
            True, 'The knowledge search found "Return the bike" as result 1.',
        )

    def test_an_article_below_the_first_results_is_not_found(self):
        searches = [search(
            article("article_1", "Lock the bike"), article("article_2", "Return the bike"),
            article("article_3", "Pay for a ride"),
        )]

        assert article_fact(["Return the bike"], searches, within_first=1) == (
            False, 'The knowledge search found "Return the bike" as result 2, not as the first result.',
        )
        assert article_fact(["Pay for a ride"], searches, within_first=2) == (
            False, 'The knowledge search found "Pay for a ride" as result 3, not in the first 2 results.',
        )
        assert article_fact(["Pay for a ride"], searches, within_first=3)[0] is True

    def test_a_miss_names_the_wanted_article_and_what_was_found(self):
        searches = [search(article("article_1", "Lock the bike")), search(article("article_1", "Lock the bike"))]

        assert article_fact(["Return the bike", "article_9"], searches) == (
            False, 'The knowledge search did not find "Return the bike", "article_9". It found: "Lock the bike".',
        )

    def test_an_article_without_a_title_is_shown_by_its_id(self):
        searches = [search(article("guides/locks.pdf", None))]

        assert article_fact(["guides/locks.pdf"], searches) == (
            True, f'The knowledge search found "{KB}#guides/locks.pdf" as result 1.',
        )

    def test_a_long_list_of_found_articles_is_counted_past_the_first_ones(self):
        found = [article(f"article_{number}", f"Guide {number}") for number in range(MAX_LISTED_ARTICLES + 2)]

        _, fact = article_fact(["Lock the bike"], [search(*found)])

        assert fact.endswith(f'"Guide {MAX_LISTED_ARTICLES - 1}" and 2 more.')

    def test_no_search_fails_and_says_so(self):
        assert article_fact(["Lock the bike"], []) == (False, NO_SEARCH)

    def test_a_search_that_found_nothing_says_so(self):
        assert article_fact(["Lock the bike"], [search()]) == (False, NO_ARTICLES)

    def test_searches_that_all_failed_say_so(self):
        assert article_fact(["Lock the bike"], [search(failed=True), search(failed=True)]) == (False, SEARCH_FAILED)
        assert article_fact(["Lock the bike"], [search(failed=True), search()]) == (False, NO_ARTICLES)


class TestWithinFirstPhrase:
    def test_the_phrase_reads_as_part_of_a_sentence(self):
        assert within_first_phrase(None) == ""
        assert within_first_phrase(1) == " as the first result"
        assert within_first_phrase(3) == " in the first 3 results"


class TestTurnRecord:
    @staticmethod
    def _case(expected_articles=None):
        return SimpleNamespace(
            id="case-1", source_conversation_id="conv-1", turn_index=0, input_data={"message": "How do I lock it?"},
            expected_output=None, expected_articles=expected_articles,
        )

    def test_the_turn_reads_its_searches_and_expected_articles_from_the_run(self):
        trace = {"output": "Use the ring lock.", "tool_events": [], "state": {
            "errors": [], "input": {},
            "nodeExecutionStatus": {"kb": search_run(source("article_1", "Lock the bike"), start=5)},
        }}

        record = turn_record(self._case(["Lock the bike"]), trace, {"message": "How do I lock it?"}, {}, [])

        assert record.expected_articles == ["Lock the bike"]
        assert [found["articles"][0]["title"] for found in record.searches] == ["Lock the bike"]

    def test_a_turn_without_searches_or_expected_articles_has_none(self):
        trace = {"output": "Hello.", "tool_events": [], "state": {"errors": [], "input": {}, "nodeExecutionStatus": {}}}

        record = turn_record(self._case(), trace, {"message": "Hi"}, {}, [])

        assert record.expected_articles == []
        assert record.searches == []
