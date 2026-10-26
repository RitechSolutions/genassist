"""Categories on datasets and evaluations: tidied, spelled as already in use, cleared with "", and filtered."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.v1.routes.test_evaluations import _category_filter
from app.schemas.eval_bundle import BundleDataset, BundleEvaluation
from app.schemas.test_suite import (
    RunWorkflowEvaluationsRequest,
    TestEvaluationUpdate,
    TestSuiteCreate,
    TestSuiteUpdate,
    tidy_category,
)
from app.services.test_suite import TestSuiteService

NOW = datetime(2026, 1, 1)


def _service(categories=()) -> TestSuiteService:
    service = TestSuiteService(
        suite_repo=AsyncMock(),
        case_repo=AsyncMock(),
        run_repo=AsyncMock(),
        result_repo=AsyncMock(),
        evaluation_repo=AsyncMock(),
        tool_rule_result_repo=AsyncMock(),
        workflow_service=AsyncMock(),
        conversation_repo=AsyncMock(),
    )
    names = list(categories)
    service.evaluation_repo.categories = AsyncMock(return_value=names)
    # As the database looks it up: any case, the first spelling if two raced.
    service.evaluation_repo.category_spelling = AsyncMock(
        side_effect=lambda category: min((n for n in names if n.lower() == category.lower()), default=None)
    )
    return service


def _suite_row(**fields):
    row = dict(
        id=uuid4(), name="Refund chats", description=None, category=None, workflow_id=None,
        default_input_metadata=None, created_at=NOW, updated_at=NOW,
    )
    return SimpleNamespace(**{**row, **fields})


def _evaluation_row(**fields):
    row = dict(
        id=uuid4(), name="Refunds", description=None, category="Refunds", suite_id=uuid4(),
        workflow_id=None, techniques=["checks"], technique_configs=None, input_metadata=None,
        run_ids=[], created_at=NOW, updated_at=NOW,
    )
    return SimpleNamespace(**{**row, **fields})


class TestTidy:
    def test_spaces_are_tidied_and_empty_means_none(self):
        assert tidy_category("  Refund   requests ") == "Refund requests"
        assert TestSuiteCreate(name="a", category="   ").category is None

    def test_an_update_clears_with_empty_text_and_keeps_it_with_none(self):
        assert TestSuiteUpdate(category=" ").category == ""
        assert TestEvaluationUpdate(category=None).category is None

    def test_a_long_category_is_refused(self):
        with pytest.raises(ValidationError):
            TestSuiteCreate(name="a", category="x" * 51)

    def test_the_route_filter_reads_none_set_and_tidies_the_name(self):
        assert _category_filter(None, True) == ""
        assert _category_filter("  Refunds ", False) == "Refunds"
        assert _category_filter("   ", False) is None
        assert _category_filter(None, False) is None

    def test_run_all_refuses_a_blank_category_rather_than_running_everything(self):
        assert RunWorkflowEvaluationsRequest(category=" Refunds ").category == "Refunds"
        assert RunWorkflowEvaluationsRequest().category is None
        with pytest.raises(ValidationError):
            RunWorkflowEvaluationsRequest(category="   ")
        # Both at once would leave one of them silently unused.
        with pytest.raises(ValidationError):
            RunWorkflowEvaluationsRequest(category="Refunds", uncategorized=True)

    def test_a_bundle_category_is_tidied_before_its_length_is_checked(self):
        # 56 characters as written, 47 once tidied.
        spaced = "a" + " " * 10 + "b" * 45
        assert BundleDataset(name="a", category=spaced).category == "a " + "b" * 45
        assert BundleEvaluation(name="a", category="  Refunds ").category == "Refunds"
        with pytest.raises(ValidationError):
            BundleEvaluation(name="a", category="x" * 51)


class TestService:
    @pytest.mark.asyncio
    async def test_categories_are_listed_alphabetically_whatever_their_case(self):
        service = _service(["refunds b", "Escalation", "Refunds a"])
        assert await service.list_categories() == ["Escalation", "Refunds a", "refunds b"]

    @pytest.mark.asyncio
    async def test_spellings_that_differ_only_in_case_are_listed_once(self):
        service = _service(["refunds", "Escalation", "Refunds"])
        assert await service.list_categories() == ["Escalation", "Refunds"]
        # A save takes the spelling the list shows.
        assert await service._known_category("REFUNDS") == "Refunds"

    @pytest.mark.asyncio
    async def test_a_new_dataset_takes_the_spelling_already_in_use(self):
        service = _service(["Refunds"])
        service.suite_repo.create = AsyncMock(side_effect=lambda orm: _suite_row(category=orm.category))
        created = await service.create_suite(TestSuiteCreate(name="Refund chats", category="refunds"))
        assert created.category == "Refunds"

    @pytest.mark.asyncio
    async def test_a_new_category_is_kept_as_typed(self):
        service = _service(["Refunds"])
        assert await service._known_category("Escalation") == "Escalation"
        assert await service._known_category("") == ""
        assert await service._known_category(None) is None

    @pytest.mark.asyncio
    async def test_an_evaluation_update_clears_the_category_with_empty_text(self):
        service = _service(["Refunds"])
        row = _evaluation_row()
        service.evaluation_repo.get_by_id = AsyncMock(return_value=row)
        service.evaluation_repo.update = AsyncMock(side_effect=lambda updated: updated)
        await service.update_evaluation(row.id, TestEvaluationUpdate(category=""))
        assert row.category is None

    @pytest.mark.asyncio
    async def test_an_evaluation_update_without_a_category_keeps_it(self):
        service = _service(["Refunds"])
        row = _evaluation_row()
        service.evaluation_repo.get_by_id = AsyncMock(return_value=row)
        service.evaluation_repo.update = AsyncMock(side_effect=lambda updated: updated)
        await service.update_evaluation(row.id, TestEvaluationUpdate(name="Refunds v2"))
        assert row.category == "Refunds"

    @pytest.mark.asyncio
    async def test_a_dataset_update_takes_the_spelling_in_use(self):
        service = _service(["Escalation"])
        row = _suite_row()
        service.suite_repo.get_by_id = AsyncMock(return_value=row)
        service.suite_repo.update = AsyncMock(side_effect=lambda updated: updated)
        await service.update_suite(row.id, TestSuiteUpdate(category="ESCALATION"))
        assert row.category == "Escalation"

    @pytest.mark.asyncio
    async def test_a_dataset_update_keeps_the_category_with_null_and_clears_it_with_empty_text(self):
        service = _service(["Escalation"])
        row = _suite_row(category="Escalation")
        service.suite_repo.get_by_id = AsyncMock(return_value=row)
        service.suite_repo.update = AsyncMock(side_effect=lambda updated: updated)
        await service.update_suite(row.id, TestSuiteUpdate.model_validate({"category": None}))
        assert row.category == "Escalation"
        await service.update_suite(row.id, TestSuiteUpdate(category=""))
        assert row.category is None

    @pytest.mark.asyncio
    async def test_run_all_asks_the_database_for_the_category_and_starts_what_it_returns(self):
        service = _service()
        rows = [_evaluation_row(category="Refunds"), _evaluation_row(category="refunds")]
        service.evaluation_repo.get_all_for_workflow = AsyncMock(return_value=rows)
        service.workflow_service.get_active_version_id = AsyncMock(return_value=uuid4())
        service._start_evaluation_run = AsyncMock(
            side_effect=lambda evaluation, *args, **kwargs: SimpleNamespace(
                id=uuid4(), suite_id=evaluation.suite_id, status="queued"
            )
        )

        results = await service.start_workflow_evaluations(uuid4(), MagicMock(), None, "REFUNDS")

        # The lists' own filter picks them, so Run all starts what the section shows.
        assert service.evaluation_repo.get_all_for_workflow.await_args.kwargs == {"category": "REFUNDS"}
        assert [result.evaluation_id for result in results] == [row.id for row in rows]

    @pytest.mark.asyncio
    async def test_the_list_and_summaries_filter_by_category(self):
        service = _service()
        service.evaluation_repo.get_page_for_workflow = AsyncMock(return_value=[])
        service.evaluation_repo.count_for_workflow = AsyncMock(side_effect=[2, 9])
        service.workflow_has_active_run = AsyncMock(return_value=False)
        page = await service.list_workflow_evaluations(None, 1, 20, None, "Refunds")
        assert service.evaluation_repo.get_page_for_workflow.await_args.args[-1] == "Refunds"
        # The workflow's own count stays unfiltered, for "2 of 9".
        assert (page.total, page.total_unfiltered) == (2, 9)

        service.evaluation_repo.count_by_effective_workflow = AsyncMock(return_value=[])
        service.evaluation_repo.get_latest_run_pointers = AsyncMock(return_value=[])
        await service.get_workflow_evaluation_summaries(None, "")
        assert service.evaluation_repo.count_by_effective_workflow.await_args.args == (None, "")
