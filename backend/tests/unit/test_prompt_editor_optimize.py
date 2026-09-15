"""The optimize route: what the rewriter is shown, what it is allowed to hand back,
and what the run records about its own spend"""

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.prompt_editor import PromptOptimizeRequest
from app.services.prompt_editor import (
    MAX_OPTIMIZE_EXAMPLES,
    TRUNCATION_MARKER,
    PromptEditorService,
)

WORKFLOW_ID = uuid4()
NODE_ID = "n1"
FIELD = "systemPrompt"
SUITE_ID = uuid4()
AGENT_NODE = {"id": NODE_ID, "type": "agentNode", "data": {"name": "A"}}
PROVIDER = SimpleNamespace(id=uuid4(), llm_model_provider="openai", llm_model="gpt-4o")

SUGGESTION = json.dumps({"improved_prompt": "Be concise.", "explanation": "Tightened."})


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


def _request(**overrides) -> PromptOptimizeRequest:
    payload = {"provider_id": PROVIDER.id, "current_prompt": "You are helpful."}
    payload.update(overrides)
    return PromptOptimizeRequest(**payload)


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
    by_id = {case.id: case for case in cases}
    case_repo.get_cases_by_ids.side_effect = lambda _suite, ids: [
        by_id[case_id] for case_id in ids if case_id in by_id
    ]
    return PromptEditorService(
        version_repo=AsyncMock(),
        config_repo=config_repo,
        suite_repo=AsyncMock(),
        case_repo=case_repo,
        workflow_repo=workflow_repo,
        db=db,
    )


def _injector(llm, provider=PROVIDER, build_error=None):
    provider_service = SimpleNamespace(get_by_id=AsyncMock(return_value=provider))
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


def _llm(reply=SUGGESTION):
    llm = AsyncMock()

    async def invoke(_messages):
        if isinstance(reply, Exception):
            raise reply
        return AIMessage(content=reply)

    llm.ainvoke.side_effect = invoke
    return llm


async def _run(service, injector, request=None):
    with patch("app.dependencies.injector.injector", injector):
        return await service.optimize_prompt(WORKFLOW_ID, NODE_ID, FIELD, request or _request())


def _human_message(llm) -> str:
    return llm.ainvoke.call_args.args[0][1].content


class TestFieldGate:
    @pytest.mark.asyncio
    async def test_a_field_the_check_cannot_reproduce_is_rejected(self):
        service = _service([_case()])

        with pytest.raises(AppException) as exc_info:
            with patch("app.dependencies.injector.injector", MagicMock()):
                await service.optimize_prompt(WORKFLOW_ID, NODE_ID, "userPrompt", _request())

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_FIELD_NOT_SUPPORTED
        assert "system prompt" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_prompt_with_no_linked_dataset_is_still_optimized(self):
        service = _service([], gold_suite_id=None)
        llm = _llm()

        result = await _run(service, _injector(llm), _request(instructions="Be shorter."))

        assert result.exploratory is True
        assert result.exposure == {"case_ids": [], "failure_case_ids": []}
        assert result.holdout_case_ids == []
        assert result.provenance.total_cases == 0
        assert "Be shorter." in _human_message(llm)


class TestExampleBudget:
    @pytest.mark.asyncio
    async def test_every_development_case_is_inlined_when_they_fit(self):
        cases = [_case(f"in{i}", {"value": f"out{i}"}) for i in range(3)]
        service = _service(cases)
        llm = _llm()

        result = await _run(service, _injector(llm))

        assert result.exposure["case_ids"] == [case.id for case in cases]
        assert result.examples_truncated is False
        message = _human_message(llm)
        assert "Input: in0\nExpected: out0" in message
        assert "## FAILED CASES" not in message

    @pytest.mark.asyncio
    async def test_more_development_cases_than_the_budget_allows_are_reported_as_cut(self):
        cases = [_case(f"in{i}", {"value": f"out{i}"}) for i in range(MAX_OPTIMIZE_EXAMPLES + 1)]
        service = _service(cases)
        llm = _llm()

        result = await _run(service, _injector(llm))

        assert len(result.exposure["case_ids"]) == MAX_OPTIMIZE_EXAMPLES
        assert result.exposure["case_ids"] == [case.id for case in cases[:MAX_OPTIMIZE_EXAMPLES]]
        assert result.examples_truncated is True

    @pytest.mark.asyncio
    async def test_a_failed_case_is_not_inlined_a_second_time_as_an_example(self):
        cases = [_case("in0", {"value": "out0"}), _case("in1", {"value": "out1"})]
        service = _service(cases)
        llm = _llm()

        result = await _run(
            service,
            _injector(llm),
            _request(failed_cases=[{"case_id": cases[0].id, "actual": "wrong"}]),
        )

        assert result.exposure["failure_case_ids"] == [cases[0].id]
        assert result.exposure["case_ids"] == [cases[0].id, cases[1].id]
        assert result.provenance.evaluated_case_ids == result.exposure["case_ids"]
        assert _human_message(llm).count("Input: in0") == 1

    @pytest.mark.asyncio
    async def test_the_rewrite_is_told_how_the_expectations_are_graded(self):
        case = _case("in0", {"value": "URL"})
        service = _service([case])
        llm = _llm()

        result = await _run(service, _injector(llm), _request(techniques=["contains"]))

        message = _human_message(llm)
        assert "## GRADING" in message
        assert "- contains: " in message
        assert "not the whole reply" in message
        assert result.provenance.techniques == ["contains"]

    @pytest.mark.asyncio
    async def test_a_rewrite_sent_no_techniques_is_told_nothing_about_grading(self):
        service = _service([_case("in0", {"value": "URL"})])
        llm = _llm()

        await _run(service, _injector(llm))

        assert "## GRADING" not in _human_message(llm)

    @pytest.mark.asyncio
    async def test_a_failing_metric_the_check_cannot_run_is_refused_before_the_model_is_built(self):
        case = _case()
        service = _service([case])
        llm = _llm()

        with pytest.raises(AppException) as exc_info:
            await _run(
                service,
                _injector(llm),
                _request(
                    failed_cases=[
                        {"case_id": case.id, "actual": "x", "failed_metrics": ["llm_judge"]}
                    ]
                ),
            )

        assert exc_info.value.error_key is ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_technique_the_check_cannot_run_is_refused_before_the_model_is_built(self):
        service = _service([_case()])
        llm = _llm()

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(llm), _request(techniques=["llm_judge"]))

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED
        llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_failure_shows_the_graded_expectation_not_the_clients_copy(self):
        case = _case("in0", {"text": "hello"})
        service = _service([case])
        llm = _llm()

        await _run(
            service,
            _injector(llm),
            _request(failed_cases=[{"case_id": case.id, "actual": "goodbye"}]),
        )

        message = _human_message(llm)
        assert "Input: in0\nExpected: hello\nGot: goodbye" in message
        assert "## FAILED CASES" in message

    @pytest.mark.asyncio
    async def test_a_failure_names_the_techniques_that_rejected_it(self):
        case = _case("in0", {"value": "URL"})
        service = _service([case])
        llm = _llm()

        await _run(
            service,
            _injector(llm),
            _request(
                techniques=["contains"],
                failed_cases=[
                    {"case_id": case.id, "actual": "no link", "failed_metrics": ["contains"]}
                ],
            ),
        )

        assert "Got: no link\nFailed: contains" in _human_message(llm)

    @pytest.mark.asyncio
    async def test_a_very_long_observed_output_is_shortened_with_a_visible_marker(self):
        case = _case("in0", {"value": "out0"})
        service = _service([case])
        llm = _llm()

        await _run(
            service,
            _injector(llm),
            _request(failed_cases=[{"case_id": case.id, "actual": "x" * 9_000}]),
        )

        message = _human_message(llm)
        assert TRUNCATION_MARKER in message
        assert "x" * 9_000 not in message

    @pytest.mark.asyncio
    async def test_an_over_sized_case_does_not_cost_a_slot_in_the_example_budget(self):
        cases = [_case("x" * 30_000, {"value": "big"})]
        cases += [_case(f"in{i}", {"value": f"out{i}"}) for i in range(MAX_OPTIMIZE_EXAMPLES + 1)]
        service = _service(cases)
        llm = _llm()

        result = await _run(service, _injector(llm))

        assert len(result.exposure["case_ids"]) == MAX_OPTIMIZE_EXAMPLES
        assert cases[0].id not in result.exposure["case_ids"]
        assert result.examples_truncated is True
        assert service.case_repo.get_cases_by_ids.await_count == 2

    @pytest.mark.asyncio
    async def test_an_example_that_does_not_fit_the_character_budget_is_skipped_whole(self):
        cases = [_case("x" * 30_000, {"value": "big"}), _case("small", {"value": "ok"})]
        service = _service(cases)
        llm = _llm()

        result = await _run(service, _injector(llm))

        assert result.exposure["case_ids"] == [cases[1].id]
        assert result.examples_truncated is True
        assert "Input: small" in _human_message(llm)


class TestCaseSplit:
    @pytest.mark.asyncio
    async def test_a_hold_out_leaves_the_rest_of_the_suite_as_development(self):
        cases = [_case(f"in{i}", {"value": f"out{i}"}) for i in range(4)]
        service = _service(cases)
        llm = _llm()

        result = await _run(
            service,
            _injector(llm),
            _request(case_split={"holdout_case_ids": [cases[0].id, cases[1].id]}),
        )

        assert result.exploratory is False
        assert result.holdout_case_ids == [cases[0].id, cases[1].id]
        assert result.exposure["case_ids"] == [cases[2].id, cases[3].id]

    @pytest.mark.asyncio
    async def test_a_hold_out_case_that_is_gone_is_refused(self):
        cases = [_case() for _ in range(4)]
        service = _service(cases)

        with pytest.raises(AppException) as exc_info:
            await _run(
                service,
                _injector(_llm()),
                _request(case_split={"holdout_case_ids": [uuid4()]}),
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_CASE_SELECTION_INVALID
        assert "hold-out cases are no longer" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_conversation_split_across_the_two_sides_is_refused(self):
        conversation = uuid4()
        cases = [_case() for _ in range(4)]
        index = [
            (cases[0].id, conversation, 0),
            (cases[1].id, conversation, 1),
            (cases[2].id, None, None),
            (cases[3].id, None, None),
        ]
        service = _service(cases, index=index)

        with pytest.raises(AppException) as exc_info:
            await _run(
                service,
                _injector(_llm()),
                _request(case_split={"holdout_case_ids": [cases[0].id]}),
            )

        assert "A conversation is split" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_failed_case_inside_the_hold_out_is_refused(self):
        cases = [_case() for _ in range(4)]
        service = _service(cases)

        with pytest.raises(AppException) as exc_info:
            await _run(
                service,
                _injector(_llm()),
                _request(
                    case_split={"holdout_case_ids": [cases[0].id, cases[1].id]},
                    failed_cases=[{"case_id": cases[0].id, "actual": "wrong"}],
                ),
            )

        assert "hold-out set" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_failed_case_that_is_gone_is_refused_before_anything_else(self):
        cases = [_case()]
        service = _service(cases)
        injector = _injector(_llm())

        with pytest.raises(AppException) as exc_info:
            await _run(
                service,
                injector,
                _request(failed_cases=[{"case_id": uuid4(), "actual": "wrong"}]),
            )

        assert "failed cases are no longer" in exc_info.value.error_detail
        assert service.case_repo.get_cases_by_ids.await_count == 0

    @pytest.mark.asyncio
    async def test_a_hold_out_of_one_conversation_does_not_meet_the_group_rule(self):
        conversation = uuid4()
        cases = [_case() for _ in range(7)]
        index = [(case.id, conversation, i) for i, case in enumerate(cases[:5])]
        index += [(cases[5].id, None, None), (cases[6].id, None, None)]
        service = _service(cases, index=index)

        with pytest.raises(AppException) as exc_info:
            await _run(
                service,
                _injector(_llm()),
                _request(case_split={"holdout_case_ids": [case.id for case in cases[:5]]}),
            )

        assert "at least two conversations or cases" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_development_side_of_one_group_does_not_meet_the_group_rule(self):
        cases = [_case() for _ in range(3)]
        service = _service(cases)

        with pytest.raises(AppException) as exc_info:
            await _run(
                service,
                _injector(_llm()),
                _request(case_split={"holdout_case_ids": [cases[0].id, cases[1].id]}),
            )

        assert "at least two conversations or cases" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_the_split_is_settled_before_a_model_is_built(self):
        cases = [_case() for _ in range(3)]
        service = _service(cases)
        injector = _injector(_llm())

        with pytest.raises(AppException):
            await _run(
                service,
                injector,
                _request(case_split={"holdout_case_ids": [cases[0].id, cases[1].id]}),
            )

        assert injector.get(MagicMock(__name__="LLMProvider")).get_model_from_provider.await_count == 0


class TestSuggestionParsing:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "reply",
        [
            '[{"improved_prompt": "x", "explanation": "y"}]',
            '{"improved_prompt": "x", "explanation": "y"} Hope that helps!',
            '```json\n{"improved_prompt": "x", "explanation": "y"}',
            '{"explanation": "y"}',
            '{"improved_prompt": 42, "explanation": "y"}',
            "Here is a much better prompt: be concise.",
        ],
    )
    async def test_a_reply_that_is_not_the_agreed_envelope_is_refused(self, reply):
        service = _service([])

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(_llm(reply)))

        assert exc_info.value.status_code == 400
        assert exc_info.value.error_key is ErrorKey.PROMPT_OPTIMIZE_UNUSABLE

    @pytest.mark.asyncio
    async def test_a_blank_suggestion_says_so_rather_than_replacing_the_prompt(self):
        service = _service([])
        reply = json.dumps({"improved_prompt": "   ", "explanation": "y"})

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(_llm(reply)))

        assert "empty prompt" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_fenced_envelope_is_accepted(self):
        service = _service([])
        reply = f"```json\n{SUGGESTION}\n```"

        result = await _run(service, _injector(_llm(reply)))

        assert result.suggested_prompt == "Be concise."
        assert result.explanation == "Tightened."


class TestProviderFailures:
    @pytest.mark.asyncio
    async def test_a_failed_model_build_is_a_502_with_a_generic_detail(self):
        service = _service([])

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(_llm(), build_error=RuntimeError("no package")))

        assert exc_info.value.status_code == 502
        assert exc_info.value.error_key is ErrorKey.PROMPT_MODEL_CALL_FAILED
        assert "no package" not in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_residency_refusal_keeps_its_own_status(self):
        service = _service([])
        refusal = AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED)

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(_llm(), build_error=refusal))

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_a_provider_outage_is_a_502_with_no_provider_detail(self):
        service = _service([])

        with pytest.raises(AppException) as exc_info:
            await _run(service, _injector(_llm(RuntimeError("rate limited by acme"))))

        assert exc_info.value.status_code == 502
        assert "acme" not in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_a_call_that_runs_past_the_budget_is_a_504(self):
        service = _service([])
        llm = AsyncMock()

        async def _never(_messages):
            await asyncio.sleep(3600)

        llm.ainvoke.side_effect = _never

        with patch("app.services.prompt_editor.OPTIMIZE_CALL_TIMEOUT_SECONDS", 0.01):
            with pytest.raises(AppException) as exc_info:
                await _run(service, _injector(llm))

        assert exc_info.value.status_code == 504
        assert exc_info.value.error_key is ErrorKey.PROMPT_EXECUTION_TIMEOUT


class TestMetering:
    @pytest.mark.asyncio
    async def test_the_rewrite_call_is_handed_over_once_under_its_own_execution_id(self):
        service = _service([])
        captured = {}

        async def _capture(ref):
            captured["ref"] = ref

        service._persist_usage = _capture
        result = await _run(service, _injector(_llm()))

        ref = captured["ref"]
        assert ref.execution_id.startswith("prompt_editor:optimize:")
        assert [entry["call_index"] for entry in ref.entries] == [0]
        assert ref.entries[0]["purpose"] == "prompt_optimize"
        assert ref.entries[0]["provider_id"] == str(PROVIDER.id)
        assert result.provenance.metering_handoff_failed is False

    @pytest.mark.asyncio
    async def test_a_paid_call_is_recorded_even_when_the_reply_is_unusable(self):
        service = _service([])
        captured = {}

        async def _capture(ref):
            captured["entries"] = list(ref.entries)

        service._persist_usage = _capture

        with pytest.raises(AppException):
            await _run(service, _injector(_llm("not json")))

        assert len(captured["entries"]) == 1

    @pytest.mark.asyncio
    async def test_a_call_that_never_answered_records_nothing(self):
        service = _service([])
        called = []
        service._persist_usage = AsyncMock(side_effect=lambda ref: called.append(ref))

        with pytest.raises(AppException):
            await _run(service, _injector(_llm(RuntimeError("down"))))

        assert called == []

    @pytest.mark.asyncio
    async def test_a_failed_hand_over_is_reported_on_the_run(self):
        service = _service([])

        async def _boom(_ref):
            raise RuntimeError("scope failed")

        service._persist_usage = _boom
        result = await _run(service, _injector(_llm()))

        assert result.provenance.metering_handoff_failed is True
        assert result.suggested_prompt == "Be concise."
