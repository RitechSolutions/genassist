"""The evaluate pipeline: what reaches the model, what reaches the user, and what
the run reports about itself"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.prompt_editor import MAX_ACTUAL_CHARS, PromptEvalRequest
from app.services.prompt_editor import TRUNCATION_MARKER, PromptEditorService

WORKFLOW_ID = uuid4()
NODE_ID = "n1"
FIELD = "systemPrompt"
SUITE_ID = uuid4()
AGENT_NODE = {"id": NODE_ID, "type": "agentNode", "data": {"name": "A"}}
PROVIDER = SimpleNamespace(id=uuid4(), llm_model_provider="openai", llm_model="gpt-4o")


def _access_row(nodes=None):
    return SimpleNamespace(
        id=WORKFLOW_ID,
        agent_id=None,
        created_by=None,
        updated_at=datetime.now(timezone.utc),
        nodes=[AGENT_NODE] if nodes is None else nodes,
        agent_visible=True,
    )


def _case(message="hi", expected=None, case_id=None):
    return SimpleNamespace(
        id=case_id or uuid4(), input_data={"message": message}, expected_output=expected
    )


def _request(**overrides) -> PromptEvalRequest:
    payload = {
        "prompt_content": "You are helpful.",
        "provider_id": PROVIDER.id,
        "techniques": ["exact_match"],
    }
    payload.update(overrides)
    return PromptEvalRequest(**payload)


def _service(cases, *, nodes=None, gold_suite_id=SUITE_ID, index=None):
    db = AsyncMock()
    db.begin_nested = MagicMock()
    db.in_transaction = MagicMock(return_value=False)
    workflow_repo = AsyncMock()
    workflow_repo.get_access_row.return_value = _access_row(nodes)
    config_repo = AsyncMock()
    config_repo.get_by_context.return_value = SimpleNamespace(gold_suite_id=gold_suite_id)
    case_repo = AsyncMock()
    case_repo.get_case_index_for_suite.return_value = (
        index if index is not None else [(case.id, None, None) for case in cases]
    )
    case_repo.get_cases_by_ids.return_value = cases
    return PromptEditorService(
        version_repo=AsyncMock(),
        config_repo=config_repo,
        suite_repo=AsyncMock(),
        case_repo=case_repo,
        workflow_repo=workflow_repo,
        db=db,
    )


def _injector(llm, provider=PROVIDER, provider_error=None, build_error=None):
    provider_service = SimpleNamespace(
        get_by_id=AsyncMock(side_effect=provider_error) if provider_error else AsyncMock(return_value=provider)
    )
    llm_provider = SimpleNamespace(
        get_model_from_provider=AsyncMock(side_effect=build_error)
        if build_error
        else AsyncMock(return_value=llm)
    )
    fake = MagicMock()
    fake.get.side_effect = lambda cls: (
        provider_service if cls.__name__ == "LlmProviderService" else llm_provider
    )
    return fake


def _llm(replies):
    llm = AsyncMock()
    pending = list(replies)

    async def invoke(_messages):
        reply = pending.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return AIMessage(content=reply)

    llm.ainvoke.side_effect = invoke
    return llm


async def _run(service, injector, request=None):
    with patch("app.dependencies.injector.injector", injector):
        return await service.evaluate_prompt(WORKFLOW_ID, NODE_ID, FIELD, request or _request())


class TestFieldGate:
    @pytest.mark.asyncio
    async def test_a_field_the_check_cannot_reproduce_is_rejected(self):
        service = _service([_case()])

        with pytest.raises(AppException) as exc_info:
            with patch("app.dependencies.injector.injector", MagicMock()):
                await service.evaluate_prompt(WORKFLOW_ID, NODE_ID, "userPrompt", _request())

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_FIELD_NOT_SUPPORTED
        assert "system prompt" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_prompt_with_no_linked_dataset_is_rejected(self):
        service = _service([], gold_suite_id=None)

        with pytest.raises(AppException) as exc_info:
            await _run(service, MagicMock())

        assert exc_info.value.error_key is ErrorKey.MISSING_PARAMETER


class TestCaseSelection:
    @pytest.mark.asyncio
    async def test_an_unknown_case_id_is_rejected_before_the_provider_is_read(self):
        service = _service([_case()])
        injector = _injector(_llm(["x"]))

        with pytest.raises(AppException) as exc_info:
            await _run(service, injector, _request(case_ids=[uuid4()]))

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_CASE_SELECTION_INVALID
        assert "Reload the cases" in exc_info.value.error_detail
        injector.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_case_deleted_between_the_two_reads_is_reported_not_dropped(self):
        wanted = [_case("a"), _case("b")]
        service = _service(wanted[:1], index=[(case.id, None, None) for case in wanted])

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(_llm(["a"])), _request(case_ids=[c.id for c in wanted]))

        assert exc_info.value.error_key is ErrorKey.PROMPT_CASE_SELECTION_INVALID
        assert str(wanted[1].id) in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_server_picked_case_that_vanishes_just_reports_a_smaller_run(self):
        picked = [_case("a", {"value": "a"}), _case("b")]
        service = _service(picked[:1], index=[(case.id, None, None) for case in picked])

        result = await _run(service, _injector(_llm(["a"])), _request(max_cases=2))

        assert result.summary.total == 1
        assert result.provenance.evaluated_case_ids == [picked[0].id]
        assert result.provenance.total_cases == 2

    @pytest.mark.asyncio
    async def test_max_cases_bounds_what_is_loaded_and_the_header_keeps_the_real_total(self):
        cases = [_case(f"m{index}") for index in range(3)]
        service = _service(cases[:2], index=[(case.id, None, None) for case in cases])

        result = await _run(service, _injector(_llm(["a", "b"])), _request(max_cases=2))

        loaded = service.case_repo.get_cases_by_ids.await_args.args[1]
        assert len(loaded) == 2
        assert result.provenance.total_cases == 3
        assert len(result.results) == 2


class TestProviderFailures:
    @pytest.mark.asyncio
    async def test_a_provider_outage_is_execution_failed_with_no_provider_detail(self):
        service = _service([_case()])
        outage = RuntimeError("401 invalid api key sk-SECRET-abc")

        result = await _run(service, _injector(_llm([outage])))

        row = result.results[0]
        assert row.status == "execution_failed"
        assert row.actual == ""
        assert row.verdict is None
        assert "sk-SECRET" not in row.error
        assert result.summary.execution_failed == 1
        assert result.summary.avg_score is None

    @pytest.mark.asyncio
    async def test_a_failed_model_build_is_a_502_with_a_generic_detail(self):
        service = _service([_case()])
        injector = _injector(None, build_error=ValueError("missing connection_data"))

        with pytest.raises(AppException) as exc_info:
            await _run(service, injector)

        assert exc_info.value.status_code == 502
        assert exc_info.value.error_key is ErrorKey.PROMPT_MODEL_CALL_FAILED
        assert "missing connection_data" not in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_residency_refusal_keeps_its_own_status(self):
        service = _service([_case()])
        residency = AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED)

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(None, build_error=residency))

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_a_rollback_that_itself_raises_still_surfaces_the_502(self):
        service = _service([_case()])
        service.db.in_transaction = MagicMock(return_value=True)
        service.db.rollback = AsyncMock(side_effect=RuntimeError("connection is gone"))

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(None, build_error=ValueError("boom")))

        assert exc_info.value.status_code == 502
        service.db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_the_provider_is_read_once_and_the_model_built_from_that_read(self):
        service = _service([_case()])
        injector = _injector(_llm(["x"]))

        result = await _run(service, injector)

        llm_provider = injector.get.side_effect(SimpleNamespace(__name__="LLMProvider"))
        llm_provider.get_model_from_provider.assert_awaited_once_with(PROVIDER)
        assert result.provenance.provider_key == "openai"
        assert result.provenance.model == "gpt-4o"


class TestScoring:
    @pytest.mark.asyncio
    async def test_the_expected_column_shows_what_the_graders_compare_against(self):
        service = _service([_case(expected={"text": "hello"})])

        result = await _run(service, _injector(_llm(["hello"])))

        assert result.results[0].expected == "hello"
        assert result.results[0].verdict == "passed"

    @pytest.mark.asyncio
    async def test_an_empty_reply_is_scored_not_failed_to_run(self):
        service = _service([_case(expected={"value": "hi"})])

        result = await _run(service, _injector(_llm([""])))

        row = result.results[0]
        assert row.status == "scored"
        assert row.verdict == "failed"

    @pytest.mark.asyncio
    async def test_a_case_with_no_expectation_marks_the_bound_checks_not_applicable(self):
        service = _service([_case(expected=None)])
        request = _request(techniques=["exact_match", "contains", "not_contains"],
                           technique_configs={"not_contains": {"phrases": ["sorry"]}})

        result = await _run(service, _injector(_llm(["all good"])), request)

        row = result.results[0]
        assert row.metrics["exact_match"]["not_applicable"] is True
        assert "no expected output" in row.metrics["exact_match"]["comment"]
        assert row.metrics["not_contains"]["passed"] is True
        assert row.verdict == "passed"
        assert row.not_applicable_metrics == 2

    @pytest.mark.asyncio
    async def test_an_empty_expectation_says_so_rather_than_failing_the_case(self):
        service = _service([_case(expected={"value": ""})])

        result = await _run(service, _injector(_llm(["anything"])), _request(techniques=["contains"]))

        assert "expected output is empty" in result.results[0].metrics["contains"]["comment"]

    @pytest.mark.asyncio
    async def test_an_empty_dict_expectation_is_real_for_json_match(self):
        service = _service([_case(expected={})])
        request = _request(techniques=["json_match", "contains"])

        result = await _run(service, _injector(_llm(["{}"])), request)

        row = result.results[0]
        assert row.metrics["json_match"]["passed"] is True
        assert row.metrics["contains"]["not_applicable"] is True

    @pytest.mark.asyncio
    async def test_a_non_object_reply_fails_json_match_while_the_text_group_grades(self):
        service = _service([_case(expected={"value": "plain words"})])
        request = _request(techniques=["json_match", "contains"])

        result = await _run(service, _injector(_llm(["plain words"])), request)

        row = result.results[0]
        assert row.metrics["json_match"]["passed"] is False
        assert row.metrics["json_match"]["comment"] == "Model output is not a single JSON object."
        assert row.metrics["contains"]["passed"] is True

    @pytest.mark.asyncio
    async def test_a_registry_that_returns_nothing_for_json_match_is_an_error_not_an_excuse(self):
        service = _service([_case(expected={"a": 1})])

        async def _evaluate(technique_ids, **_kwargs):
            return {} if list(technique_ids) == ["json_match"] else {
                "contains": {"key": "contains", "score": True, "passed": True}
            }

        service.evaluators.evaluate = _evaluate
        result = await _run(
            service, _injector(_llm(['{"a": 1}'])), _request(techniques=["contains", "json_match"])
        )

        row = result.results[0]
        assert row.metrics["json_match"]["error"] is True
        assert row.errored_metrics == 1
        assert row.verdict == "inconclusive"

    @pytest.mark.asyncio
    async def test_an_awaiting_input_envelope_does_not_show_human_in_the_loop_copy(self):
        service = _service([_case(expected={"status": "awaiting_input"})])

        result = await _run(
            service, _injector(_llm(['{"status": "awaiting_input"}'])), _request(techniques=["json_match"])
        )

        comment = result.results[0].metrics["json_match"].get("comment") or ""
        assert "human input" not in comment


class TestWireBounds:
    @pytest.mark.asyncio
    async def test_a_long_input_is_sent_in_full_and_returned_cut_with_the_marker(self):
        long_message = "q" * 20_000
        service = _service([_case(message=long_message)])
        llm = _llm(["ok"])

        result = await _run(service, _injector(llm))

        sent = llm.ainvoke.await_args.args[0][1].content
        assert len(sent) == 20_000
        row = result.results[0]
        assert len(row.input) == MAX_ACTUAL_CHARS
        assert row.input.endswith(TRUNCATION_MARKER)

    @pytest.mark.asyncio
    async def test_a_long_reply_is_graded_in_full_and_returned_at_the_bound(self):
        reply = "z" * 40_000
        service = _service([_case(expected={"value": reply})])

        result = await _run(service, _injector(_llm([reply])))

        row = result.results[0]
        assert len(row.actual) == MAX_ACTUAL_CHARS
        assert row.actual_truncated is True
        assert row.verdict == "passed"


    @pytest.mark.asyncio
    async def test_a_metric_that_echoes_the_reply_is_bounded_too(self):
        reply = "z" * 40_000
        service = _service([_case(expected={"value": reply})])

        result = await _run(service, _injector(_llm([reply])), _request(techniques=["field_equals"]))

        metric = result.results[0].metrics["field_equals"]
        assert len(metric["actual"]) == MAX_ACTUAL_CHARS
        assert metric["actual"].endswith(TRUNCATION_MARKER)
        assert len(metric["expected"]) == MAX_ACTUAL_CHARS

    @pytest.mark.asyncio
    async def test_a_grounding_model_that_could_not_load_says_so(self, monkeypatch):
        import app.services.prompt_editor as module

        monkeypatch.setattr(module.evaluation_nli_model, "is_loaded", lambda _name=None: False)
        service = _service([_case("a", {"value": "a"})])

        async def _evaluate(technique_ids, **_kwargs):
            return {
                "nli_eval": {
                    "key": "nli_eval",
                    "score": None,
                    "passed": False,
                    "error": True,
                    "comment": "Evaluator failed to run. Check server logs for details.",
                }
            }

        service.evaluators.evaluate = _evaluate
        result = await _run(service, _injector(_llm(["a"])), _request(techniques=["nli_eval"]))

        comment = result.results[0].metrics["nli_eval"]["comment"]
        assert "grounding model is still loading" in comment
        assert result.results[0].verdict == "inconclusive"


class TestBudget:
    @pytest.mark.asyncio
    async def test_a_run_out_of_time_still_scores_every_response_it_paid_for(self):
        cases = [_case("a", {"value": "a"}), _case("b", {"value": "b"})]
        service = _service(cases)
        import app.services.prompt_editor as module

        real_budget = module.Budget
        calls = {"n": 0}

        class OneCallBudget(real_budget):
            def remaining(self):
                calls["n"] += 1
                return 10.0 if calls["n"] == 1 else 0.0

        with patch.object(module, "Budget", OneCallBudget):
            result = await _run(service, _injector(_llm(["a", "b"])))

        statuses = [row.status for row in result.results]
        assert statuses == ["scored", "skipped"]
        assert result.results[0].verdict == "passed"
        assert result.provenance.deadline_hit is True
        assert result.summary.skipped == 1


    @pytest.mark.asyncio
    async def test_a_case_woken_after_the_deadline_never_starts_a_call(self):
        import app.services.prompt_editor as module

        concurrency = module.PROMPT_CHECK_CONCURRENCY
        cases = [_case(f"m{index}", {"value": f"m{index}"}) for index in range(concurrency + 2)]
        service = _service(cases)
        llm = AsyncMock()

        async def slow_invoke(_messages):
            await asyncio.sleep(0.3)
            return AIMessage(content="m0")

        llm.ainvoke.side_effect = slow_invoke

        class ShortBudget(module.Budget):
            def __init__(self, _seconds):
                super().__init__(0.05)

        with patch.object(module, "Budget", ShortBudget):
            result = await _run(service, _injector(llm))

        assert llm.ainvoke.call_count == concurrency
        assert result.summary.skipped == 2
        assert result.provenance.deadline_hit is True


    @pytest.mark.asyncio
    async def test_a_call_cut_by_the_run_budget_does_not_blame_the_provider(self):
        import app.services.prompt_editor as module

        service = _service([_case("a", {"value": "a"})])
        llm = AsyncMock()

        async def slow_invoke(_messages):
            await asyncio.sleep(0.3)
            return AIMessage(content="a")

        llm.ainvoke.side_effect = slow_invoke

        class ShortBudget(module.Budget):
            def __init__(self, _seconds):
                super().__init__(0.05)

        with patch.object(module, "Budget", ShortBudget):
            result = await _run(service, _injector(llm))

        row = result.results[0]
        assert row.status == "execution_failed"
        assert "time budget" in row.error
        assert result.provenance.deadline_hit is True


class TestGroundingCheck:
    @pytest.mark.asyncio
    async def test_an_exhausted_scoring_budget_reports_the_grounding_model_not_a_failure(self):
        import app.services.prompt_editor as module

        service = _service([_case("a", {"value": "a"})])
        request = _request(techniques=["contains", "nli_eval"])

        class SpentScoreBudget(module.Budget):
            def remaining(self):
                return 0.0 if self._deadline_seconds == module.PROMPT_CHECK_SCORE_BUDGET_SECONDS else 10.0

            def __init__(self, seconds):
                self._deadline_seconds = seconds
                super().__init__(seconds)

        with patch.object(module, "Budget", SpentScoreBudget):
            result = await _run(service, _injector(_llm(["a"])), request)

        row = result.results[0]
        assert row.metrics["nli_eval"]["error"] is True
        assert "grounding model is still loading" in row.metrics["nli_eval"]["comment"]
        assert row.metrics["contains"]["passed"] is True
        assert result.provenance.deadline_hit is True

    @pytest.mark.asyncio
    async def test_a_loaded_grounding_model_gets_the_plain_timeout_text(self, monkeypatch):
        import app.services.prompt_editor as module

        monkeypatch.setattr(module.evaluation_nli_model, "is_loaded", lambda _name=None: True)
        assert module._scoring_timeout_text(["nli_eval"]) == "Scoring timed out."
        assert module._scoring_timeout_text([]) == "Scoring timed out."


class TestMetering:
    @pytest.mark.asyncio
    async def test_the_run_is_handed_over_once_with_one_entry_per_answered_case(self):
        cases = [_case("a", {"value": "a"}), _case("b", {"value": "b"}), _case("c")]
        service = _service(cases)
        captured = {}

        async def _fake_persist(ref):
            captured["ref"] = ref

        service._persist_usage = _fake_persist
        result = await _run(service, _injector(_llm(["a", "b", RuntimeError("down")])))

        ref = captured["ref"]
        assert ref.execution_id.startswith("prompt_editor:")
        assert [entry["call_index"] for entry in ref.entries] == [0, 1]
        assert {entry["purpose"] for entry in ref.entries} == {"prompt_check"}
        assert result.provenance.metering_handoff_failed is False

    @pytest.mark.asyncio
    async def test_the_ledger_entry_carries_what_the_recorder_reads(self, monkeypatch):
        import app.modules.workflow.engine.llm_usage_tracking as tracking
        import app.services.llm_usage_recorder as recorder_module

        captured = {}

        class FakeRecorder:
            async def record_evaluation_calls(self, execution_id, entries, **kwargs):
                captured["execution_id"] = execution_id
                captured["entries"] = entries
                captured["kwargs"] = kwargs

        async def _resolve(provider_id, cache=None):
            return ("openai", "gpt-4o")

        monkeypatch.setattr(recorder_module, "LlmUsageRecorder", FakeRecorder)
        monkeypatch.setattr(tracking, "resolve_provider_model", _resolve)

        service = _service([_case("a", {"value": "a"})])
        result = await _run(service, _injector(_llm(["a"])))

        entry = captured["entries"][0]
        assert set(entry) == {"call_index", "provider_id", "purpose", "usage", "provider", "model", "llm_provider_id"}
        assert entry["purpose"] == "prompt_check"
        assert (entry["provider"], entry["model"]) == ("openai", "gpt-4o")
        assert entry["llm_provider_id"] == PROVIDER.id
        assert captured["kwargs"]["source"] == "prompt_editor"
        assert captured["kwargs"]["workflow_id"] == WORKFLOW_ID
        assert result.provenance.metering_handoff_failed is False

    @pytest.mark.asyncio
    async def test_spend_is_handed_over_even_when_scoring_blows_up(self):
        service = _service([_case("a", {"value": "a"})])
        captured = {}

        async def _capture(ref):
            captured["entries"] = list(ref.entries)

        service._persist_usage = _capture
        service._score_all = AsyncMock(side_effect=RuntimeError("scoring exploded"))

        with pytest.raises(RuntimeError):
            await _run(service, _injector(_llm(["a"])))

        assert len(captured["entries"]) == 1

    @pytest.mark.asyncio
    async def test_a_failed_hand_over_is_reported_on_the_run(self):
        service = _service([_case("a", {"value": "a"})])

        async def _boom(_ref):
            raise RuntimeError("scope failed")

        service._persist_usage = _boom
        result = await _run(service, _injector(_llm(["a"])))

        assert result.provenance.metering_handoff_failed is True
        assert result.results[0].verdict == "passed"
