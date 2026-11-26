"""A turn's expected articles: how they are cleaned, limited, stored and cleared."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.test_suite import (
    MAX_ARTICLE_NAME_LENGTH,
    MAX_EXPECTED_ARTICLES,
    TestCaseCreate,
    TestCaseUpdate,
)
from app.services.test_suite import TestSuiteService


def _create(expected_articles) -> TestCaseCreate:
    return TestCaseCreate(suite_id=uuid4(), input_data={"message": "How do I lock it?"}, expected_articles=expected_articles)


def _service() -> TestSuiteService:
    return TestSuiteService(
        suite_repo=AsyncMock(),
        case_repo=AsyncMock(),
        run_repo=AsyncMock(),
        result_repo=AsyncMock(),
        evaluation_repo=AsyncMock(),
        tool_rule_result_repo=AsyncMock(),
        workflow_service=AsyncMock(),
        conversation_repo=AsyncMock(),
    )


class TestExpectedArticlesField:
    def test_names_are_trimmed_and_kept_once_in_order(self):
        assert _create([" Lock the bike ", "article_7", "Lock the bike"]).expected_articles == [
            "Lock the bike", "article_7",
        ]

    @pytest.mark.parametrize("empty", [None, [], ["", "   "]])
    def test_no_names_are_stored_as_none(self, empty):
        assert _create(empty).expected_articles is None

    @pytest.mark.parametrize("not_a_list_of_text", ["Lock the bike", ["Lock the bike", 7], {"title": "Lock the bike"}])
    def test_anything_but_a_list_of_text_is_refused(self, not_a_list_of_text):
        with pytest.raises(ValidationError, match="must be a list of article titles or ids"):
            _create(not_a_list_of_text)

    def test_more_articles_than_the_limit_are_refused(self):
        names = [f"Guide {number}" for number in range(MAX_EXPECTED_ARTICLES + 1)]

        assert len(_create(names[:-1]).expected_articles) == MAX_EXPECTED_ARTICLES
        with pytest.raises(ValidationError, match=f"at most {MAX_EXPECTED_ARTICLES} articles"):
            _create(names)

    def test_a_name_longer_than_the_limit_is_refused(self):
        assert _create(["a" * MAX_ARTICLE_NAME_LENGTH]).expected_articles == ["a" * MAX_ARTICLE_NAME_LENGTH]
        with pytest.raises(ValidationError, match=f"at most {MAX_ARTICLE_NAME_LENGTH} characters"):
            _create(["a" * (MAX_ARTICLE_NAME_LENGTH + 1)])

    def test_an_update_changes_them_only_when_they_are_sent(self):
        assert "expected_articles" not in TestCaseUpdate(weight=2).model_dump(exclude_unset=True)
        assert TestCaseUpdate(expected_articles=[]).model_dump(exclude_unset=True) == {"expected_articles": None}


class TestStoringExpectedArticles:
    @pytest.mark.asyncio
    async def test_a_new_turn_is_stored_with_its_expected_articles(self):
        service = _service()
        service.case_repo.create.side_effect = lambda model: SimpleNamespace(
            id=uuid4(), suite_id=model.suite_id, input_data=model.input_data, expected_output=model.expected_output,
            expected_articles=model.expected_articles, tags=model.tags, weight=model.weight,
            source_conversation_id=model.source_conversation_id, turn_index=model.turn_index,
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )

        stored = await service.add_case(_create(["Lock the bike"]))

        assert stored.expected_articles == ["Lock the bike"]

    @pytest.mark.asyncio
    async def test_an_edit_can_clear_the_expected_articles(self):
        service = _service()
        case = SimpleNamespace(
            id=uuid4(), suite_id=uuid4(), input_data={"message": "How do I lock it?"}, expected_output=None,
            expected_articles=["Lock the bike"], tags=None, weight=None, source_conversation_id=None, turn_index=None,
            created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        service.case_repo.get_by_id.return_value = case
        service.case_repo.update.side_effect = lambda model: model

        stored = await service.update_case(case.id, TestCaseUpdate(expected_articles=[]))

        assert stored.expected_articles is None
