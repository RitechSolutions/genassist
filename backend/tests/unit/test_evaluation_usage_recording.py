"""Unit tests for collecting judge LLM usage and flushing it outside the scoring timeout"""

import asyncio
import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.services.llm_usage_recorder as recorder_module
import app.services.test_suite as test_suite_module
from app.modules.workflow.engine import llm_usage_tracking
from app.modules.workflow.llm.fallback_exceptions import FALLBACK_PROVIDER_ID_KEY
from app.schemas.workflow import WorkflowInDB
from app.services.test_suite import EvaluationUsageRef, SimpleEvaluatorRegistry

_JUDGE_JSON = '{"score": 0.9, "reason": "grounded"}'
_USAGE = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}

_RUBRIC = {"rubric": "Is the reply professional?"}
_PROVENANCE_LLM = {"provenance_mode": "llm", "context_source": "expected_output"}


class FakeResponse:
    def __init__(self, usage=_USAGE, content=_JUDGE_JSON, metadata=None):
        self.content = content
        self.usage_metadata = usage
        self.response_metadata = metadata or {}


class FakeLlm:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def ainvoke(self, _messages):
        self.calls += 1
        response = self._responses.pop(0) if self._responses else FakeResponse()
        if isinstance(response, Exception):
            raise response
        return response


class FakeLlmProvider:
    def __init__(self, llm):
        self._llm = llm
        self.requested_ids = []
        self.fallback_requests = 0

    async def get_model(self, provider_id=None):
        self.requested_ids.append(provider_id)
        return self._llm

    async def get_model_with_fallback(self, provider_ids, retry_policy=None):
        self.fallback_requests += 1
        return self._llm


@pytest.fixture
def judge_llm(monkeypatch):

    def _install(*responses):
        llm = FakeLlm(responses or [FakeResponse()])
        llm.provider = FakeLlmProvider(llm)
        monkeypatch.setattr(test_suite_module.injector, "get", lambda _cls: llm.provider)
        return llm

    return _install


def _service():
    return test_suite_module.TestSuiteService(None, None, None, None, None, None, None, None)


def _ref() -> EvaluationUsageRef:
    return EvaluationUsageRef(execution_id=f"eval:{uuid4()}", workflow_id=uuid4(), agent_id=uuid4())


async def _evaluate(techniques, *, usage_ref, configs, outputs="A polite, complete reply."):
    return await SimpleEvaluatorRegistry().evaluate(
        techniques,
        inputs={"message": "hello"},
        outputs=outputs,
        reference_outputs="A polite, complete reply.",
        technique_configs=configs,
        usage_ref=usage_ref,
    )


class TestUsageRefIdentity:

    def test_execution_id_is_prefixed_and_fits_the_column(self):
        ref = EvaluationUsageRef(execution_id=f"eval:{uuid4()}")
        assert ref.execution_id.startswith("eval:")
        assert len(ref.execution_id) <= 64, "the ledger column is String(64)"

    def test_each_ref_owns_its_own_entry_list(self):
        first, second = EvaluationUsageRef("eval:a"), EvaluationUsageRef("eval:b")
        first.entries.append({"call_index": 0})
        assert second.entries == []


class TestJudgeCollection:

    @pytest.mark.asyncio
    async def test_llm_judge_collects_one_entry_at_its_technique_position(self, judge_llm):
        judge_llm()
        ref = _ref()

        await _evaluate(["no_errors", "llm_judge"], usage_ref=ref, configs={"llm_judge": _RUBRIC})

        assert len(ref.entries) == 1
        entry = ref.entries[0]
        assert entry["purpose"] == "llm_judge"
        assert entry["call_index"] == 1
        assert entry["usage"] == _USAGE

    @pytest.mark.asyncio
    async def test_provenance_judge_collects_under_its_own_purpose(self, judge_llm):
        judge_llm()
        ref = _ref()

        await _evaluate(["provenance_eval"], usage_ref=ref, configs={"provenance_eval": _PROVENANCE_LLM})

        assert [e["purpose"] for e in ref.entries] == ["provenance_judge"]
        assert ref.entries[0]["call_index"] == 0

    @pytest.mark.asyncio
    async def test_both_methods_bill_separately_in_one_case(self, judge_llm):
        llm = judge_llm(FakeResponse(), FakeResponse())
        ref = _ref()

        await _evaluate(
            ["provenance_eval", "llm_judge"],
            usage_ref=ref,
            configs={"provenance_eval": _PROVENANCE_LLM, "llm_judge": _RUBRIC},
        )

        assert llm.calls == 2
        assert [(e["call_index"], e["purpose"]) for e in ref.entries] == [
            (0, "provenance_judge"),
            (1, "llm_judge"),
        ]

    @pytest.mark.asyncio
    async def test_a_duplicated_technique_bills_both_calls_at_distinct_positions(self, judge_llm):
        llm = judge_llm(FakeResponse(), FakeResponse())
        ref = _ref()

        await _evaluate(["llm_judge", "llm_judge"], usage_ref=ref, configs={"llm_judge": _RUBRIC})

        assert llm.calls == 2
        assert [e["call_index"] for e in ref.entries] == [0, 1]

    @pytest.mark.asyncio
    async def test_a_multi_rule_judge_bills_every_rule_at_a_distinct_index(self, judge_llm):
        """Each rule of a multi-rule llm_judge makes its own real LLM call; without
        a distinct call_index per rule, the recorder's (execution_id, call_index)
        upsert silently drops every rule but one."""
        llm = judge_llm(FakeResponse(), FakeResponse(), FakeResponse())
        ref = _ref()

        await _evaluate(
            ["llm_judge", "provenance_eval"],
            usage_ref=ref,
            configs={
                "llm_judge": {
                    "rules": [
                        {"label": "Tone", "rubric": "Polite?", "min_score": 0.5},
                        {"label": "Completeness", "rubric": "Complete?", "min_score": 0.5},
                    ]
                },
                "provenance_eval": _PROVENANCE_LLM,
            },
        )

        assert llm.calls == 3
        call_indexes = [e["call_index"] for e in ref.entries]
        assert len(set(call_indexes)) == 3, "every rule's call must get its own index"
        # The technique after a multi-rule judge still lands on its own position,
        # unaffected by how many calls the multi-rule technique before it made.
        assert [e["purpose"] for e in ref.entries][-1] == "provenance_judge"
        assert call_indexes[-1] == 1

    @pytest.mark.asyncio
    async def test_a_skipped_judge_never_shifts_another_method_onto_its_index(self, judge_llm):
        judge_llm()
        ref = _ref()

        metrics = await _evaluate(
            ["provenance_eval", "llm_judge"],
            usage_ref=ref,
            configs={"provenance_eval": _PROVENANCE_LLM, "llm_judge": _RUBRIC},
            outputs="",
        )

        assert metrics["provenance_eval"]["not_evaluated"] is True
        assert [(e["call_index"], e["purpose"]) for e in ref.entries] == [(1, "llm_judge")]

    @pytest.mark.asyncio
    async def test_a_judge_without_usage_metadata_still_collects_the_call(self, judge_llm):
        judge_llm(FakeResponse(usage=None))
        ref = _ref()

        await _evaluate(["llm_judge"], usage_ref=ref, configs={"llm_judge": _RUBRIC})

        assert len(ref.entries) == 1 and ref.entries[0]["usage"] is None

    @pytest.mark.asyncio
    async def test_a_malformed_judge_answer_still_bills_its_tokens(self, judge_llm):
        judge_llm(FakeResponse(content="not json at all"))
        ref = _ref()

        metrics = await _evaluate(["llm_judge"], usage_ref=ref, configs={"llm_judge": _RUBRIC})

        assert metrics["llm_judge"]["error"] is True
        assert len(ref.entries) == 1

    @pytest.mark.asyncio
    async def test_a_failed_provider_call_collects_nothing(self, judge_llm):
        judge_llm(RuntimeError("provider down"))
        ref = _ref()

        metrics = await _evaluate(["llm_judge"], usage_ref=ref, configs={"llm_judge": _RUBRIC})

        assert metrics["llm_judge"]["error"] is True
        assert ref.entries == []

    @pytest.mark.asyncio
    async def test_the_prompt_editor_path_collects_nothing(self, judge_llm, caplog):
        llm = judge_llm()

        with caplog.at_level(logging.WARNING, logger=test_suite_module.__name__):
            await SimpleEvaluatorRegistry().evaluate(
                ["llm_judge"],
                inputs={},
                outputs="Hello",
                reference_outputs=None,
                technique_configs={"llm_judge": _RUBRIC},
            )

        assert llm.calls == 1, "the judge still runs; only metering is absent"
        assert [r for r in caplog.records if r.name == test_suite_module.__name__] == [], (
            "a ref-less judge skips collection instead of failing into it"
        )

    @pytest.mark.asyncio
    async def test_metering_leaves_the_metrics_untouched(self, judge_llm):
        judge_llm(*[FakeResponse() for _ in range(4)])
        techniques = ["exact_match", "provenance_eval", "llm_judge"]
        configs = {"provenance_eval": _PROVENANCE_LLM, "llm_judge": _RUBRIC}
        ref = _ref()

        metered = await _evaluate(techniques, usage_ref=ref, configs=configs)
        unmetered = await _evaluate(techniques, usage_ref=None, configs=configs)

        assert metered == unmetered
        assert len(ref.entries) == 2

    @pytest.mark.asyncio
    async def test_the_configured_provider_is_recorded_when_nothing_failed_over(self, judge_llm):
        configured = str(uuid4())
        judge_llm()
        ref = _ref()

        await _evaluate(
            ["llm_judge"], usage_ref=ref, configs={"llm_judge": {**_RUBRIC, "llm_provider_id": configured}}
        )

        assert ref.entries[0]["provider_id"] == configured

    @pytest.mark.asyncio
    async def test_a_failed_over_answer_bills_the_provider_that_replied(self, judge_llm):
        configured, responded = str(uuid4()), str(uuid4())
        judge_llm(FakeResponse(metadata={FALLBACK_PROVIDER_ID_KEY: responded}))
        ref = _ref()

        await _evaluate(
            ["llm_judge"], usage_ref=ref, configs={"llm_judge": {**_RUBRIC, "llm_provider_id": configured}}
        )

        assert ref.entries[0]["provider_id"] == responded, "pricing follows the provider that answered"

    @pytest.mark.asyncio
    async def test_judges_resolve_one_provider_and_never_a_fallback_chain(self, judge_llm):
        configured = str(uuid4())
        llm = judge_llm()

        metrics = await _evaluate(
            ["llm_judge"], usage_ref=_ref(), configs={"llm_judge": {**_RUBRIC, "llm_provider_id": configured}}
        )

        assert metrics["llm_judge"]["score"] == 0.9
        assert llm.provider.requested_ids == [configured]
        assert llm.provider.fallback_requests == 0

    @pytest.mark.asyncio
    async def test_non_llm_techniques_collect_nothing(self, judge_llm):
        judge_llm()
        ref = _ref()

        await _evaluate(["exact_match", "no_errors"], usage_ref=ref, configs={})

        assert ref.entries == []


class TestFlush:

    @staticmethod
    def _capture_recorder(monkeypatch):
        recorded = []

        class FakeRecorder:
            async def record_evaluation_calls(self, execution_id, entries, *, workflow_id=None, agent_id=None, **_):
                recorded.append((execution_id, entries, workflow_id, agent_id))

        monkeypatch.setattr(recorder_module, "LlmUsageRecorder", FakeRecorder)
        return recorded

    @staticmethod
    def _stub_resolution(monkeypatch, mapping):
        async def _resolve(provider_id, cache=None):
            key = str(provider_id) if provider_id else ""
            if cache is not None and key in cache:
                return cache[key]
            resolved = mapping.get(key, ("", ""))
            if cache is not None:
                cache[key] = resolved
            return resolved

        monkeypatch.setattr(llm_usage_tracking, "resolve_provider_model", _resolve)

    @pytest.mark.asyncio
    async def test_flush_resolves_identity_and_records_the_case_once(self, monkeypatch):
        provider_id = uuid4()
        recorded = self._capture_recorder(monkeypatch)
        self._stub_resolution(monkeypatch, {str(provider_id): ("openai", "gpt-4o")})
        ref = _ref()
        ref.entries = [
            {"call_index": 0, "provider_id": str(provider_id), "purpose": "llm_judge", "usage": _USAGE},
            {"call_index": 1, "provider_id": str(provider_id), "purpose": "provenance_judge", "usage": _USAGE},
        ]

        await _service()._flush_judge_usage(ref, {}, {"timed_out": False})

        assert len(recorded) == 1, "one recorder invocation per evaluated case"
        execution_id, entries, workflow_id, agent_id = recorded[0]
        assert execution_id == ref.execution_id and workflow_id == ref.workflow_id
        assert agent_id == ref.agent_id, "the owning agent reaches the recorder, not just the workflow"
        assert [(e["provider"], e["model"]) for e in entries] == [("openai", "gpt-4o")] * 2
        assert {e["llm_provider_id"] for e in entries} == {provider_id}

    @pytest.mark.asyncio
    async def test_provider_names_are_resolved_once_per_run(self, monkeypatch):
        provider_id = uuid4()
        self._capture_recorder(monkeypatch)
        lookups = []

        async def _resolve(pid, cache=None):
            key = str(pid) if pid else ""
            if cache is not None and key in cache:
                return cache[key]
            lookups.append(key)
            resolved = ("openai", "gpt-4o")
            if cache is not None:
                cache[key] = resolved
            return resolved

        monkeypatch.setattr(llm_usage_tracking, "resolve_provider_model", _resolve)
        cache, state = {}, {"timed_out": False}
        service = _service()

        for _ in range(3):
            ref = _ref()
            ref.entries = [{"call_index": 0, "provider_id": str(provider_id), "purpose": "llm_judge", "usage": _USAGE}]
            await service._flush_judge_usage(ref, cache, state)

        assert lookups == [str(provider_id)], "the run-level cache serves later cases"

    @pytest.mark.asyncio
    async def test_a_judge_without_a_configured_provider_falls_back_to_the_default(self, monkeypatch):
        default_id = uuid4()
        recorded = self._capture_recorder(monkeypatch)
        self._stub_resolution(monkeypatch, {str(default_id): ("anthropic", "claude-sonnet")})
        service = _service()
        monkeypatch.setattr(service, "_default_judge_provider_id", lambda: _async(str(default_id)))
        ref = _ref()
        ref.entries = [{"call_index": 0, "provider_id": None, "purpose": "llm_judge", "usage": _USAGE}]

        await service._flush_judge_usage(ref, {}, {"timed_out": False})

        entry = recorded[0][1][0]
        assert (entry["provider"], entry["model"]) == ("anthropic", "claude-sonnet")
        assert entry["llm_provider_id"] == default_id

    @pytest.mark.asyncio
    async def test_an_unresolvable_default_stays_counted_but_unpriced(self, monkeypatch):
        recorded = self._capture_recorder(monkeypatch)
        self._stub_resolution(monkeypatch, {})
        service = _service()
        monkeypatch.setattr(service, "_default_judge_provider_id", lambda: _async(None))
        ref = _ref()
        ref.entries = [{"call_index": 0, "provider_id": None, "purpose": "llm_judge", "usage": _USAGE}]

        await service._flush_judge_usage(ref, {}, {"timed_out": False})

        entry = recorded[0][1][0]
        assert (entry["provider"], entry["model"]) == ("", "")
        assert entry["llm_provider_id"] is None

    @pytest.mark.asyncio
    async def test_nothing_collected_means_nothing_recorded(self, monkeypatch):
        recorded = self._capture_recorder(monkeypatch)

        await _service()._flush_judge_usage(_ref(), {}, {"timed_out": False})

        assert recorded == []

    @pytest.mark.asyncio
    async def test_an_execution_without_an_id_is_simply_unmetered(self, monkeypatch):
        # A state carrying no execution id has no ledger key; scoring must not notice.
        recorded = self._capture_recorder(monkeypatch)

        await _service()._flush_judge_usage(None, {}, {"timed_out": False})

        assert recorded == []

    @pytest.mark.asyncio
    async def test_a_flush_failure_never_escapes(self, monkeypatch):
        async def boom(*_args, **_kwargs):
            raise RuntimeError("recorder exploded")

        monkeypatch.setattr(test_suite_module.TestSuiteService, "_persist_judge_usage", boom)
        ref = _ref()
        ref.entries = [{"call_index": 0, "provider_id": None, "purpose": "llm_judge", "usage": _USAGE}]
        state = {"timed_out": False}

        await _service()._flush_judge_usage(ref, {}, state)

        assert state["timed_out"] is False, "an ordinary failure keeps metering on for later cases"

    @pytest.mark.asyncio
    async def test_the_first_metering_timeout_latches_off_the_rest_of_the_run(self, monkeypatch):
        monkeypatch.setattr(test_suite_module, "EVALUATION_USAGE_FLUSH_TIMEOUT_SECONDS", 0.01)
        attempts = []

        async def hang(*_args, **_kwargs):
            attempts.append(1)
            await asyncio.sleep(5)

        monkeypatch.setattr(test_suite_module.TestSuiteService, "_persist_judge_usage", hang)
        state = {"timed_out": False}
        service = _service()

        for _ in range(3):
            ref = _ref()
            ref.entries = [{"call_index": 0, "provider_id": None, "purpose": "llm_judge", "usage": _USAGE}]
            await service._flush_judge_usage(ref, {}, state)

        assert state["timed_out"] is True
        assert len(attempts) == 1, "later cases skip metering instead of paying the timeout again"


def _async(value):
    async def _wrapped():
        return value

    return _wrapped()


class TestDefaultProviderLookup:

    @pytest.mark.asyncio
    async def test_returns_the_first_provider_row(self, monkeypatch):
        provider_id = uuid4()

        class FakeProviderService:
            async def get_all(self):
                return [SimpleNamespace(id=provider_id), SimpleNamespace(id=uuid4())]

        monkeypatch.setattr(test_suite_module.injector, "get", lambda _cls: FakeProviderService())

        assert await _service()._default_judge_provider_id() == str(provider_id)

    @pytest.mark.asyncio
    async def test_no_providers_resolve_to_none(self, monkeypatch):
        class EmptyProviderService:
            async def get_all(self):
                return []

        monkeypatch.setattr(test_suite_module.injector, "get", lambda _cls: EmptyProviderService())

        assert await _service()._default_judge_provider_id() is None

    @pytest.mark.asyncio
    async def test_a_lookup_failure_degrades_to_none(self, monkeypatch):
        def boom(_cls):
            raise RuntimeError("providers unavailable")

        monkeypatch.setattr(test_suite_module.injector, "get", boom)

        assert await _service()._default_judge_provider_id() is None


class EngineStub:

    def __init__(self, config):
        self.workflow_id = config["id"]

    async def execute_from_node(self, **_kwargs):
        return SimpleNamespace(
            execution_id=uuid4(),
            status="completed",
            output="ok",
            format_state_as_response=lambda: {"state": {}},
        )


class EvaluatorSpy:
    def __init__(self):
        self.usage_refs = []

    def default_techniques(self):
        return ["contains"]

    async def evaluate(self, _techniques, *, usage_ref=None, **_kwargs):
        self.usage_refs.append(usage_ref)
        return {}


class TestRunAttribution:

    @staticmethod
    def _workflow(workflow_id, agent_id):
        now = datetime(2026, 7, 30, tzinfo=timezone.utc)
        return WorkflowInDB(
            id=workflow_id,
            name="historical version",
            version="1",
            nodes=[],
            edges=[],
            agent_id=agent_id,
            created_at=now,
            updated_at=now,
        )

    @pytest.mark.asyncio
    async def test_a_run_tags_judge_usage_with_the_evaluated_versions_owner(self, monkeypatch):
        workflow_id, owner_id = uuid4(), uuid4()
        monkeypatch.setattr(test_suite_module, "WorkflowEngine", EngineStub)

        async def _accept(*_args, **_kwargs):
            return None

        service = _service()
        spy = EvaluatorSpy()
        service.evaluators = spy
        service.run_repo = SimpleNamespace(update=_accept)
        service.result_repo = SimpleNamespace(create=_accept)
        case = SimpleNamespace(
            id=uuid4(),
            source_conversation_id=None,
            turn_index=0,
            created_at=0,
            input_data={"message": "hello"},
            expected_output=None,
        )
        monkeypatch.setattr(service, "list_cases_for_suite", lambda _suite_id: _async([case]))
        suite = SimpleNamespace(id=uuid4(), default_input_metadata=None)
        run = SimpleNamespace(id=uuid4(), status="pending", techniques=["contains"], summary_metrics=None)

        await service._execute_run_inner(suite, self._workflow(workflow_id, owner_id), run)

        assert len(spy.usage_refs) == 1
        usage_ref = spy.usage_refs[0]
        assert usage_ref.agent_id == owner_id, "the version's own agent, whichever version is active now"
        assert usage_ref.workflow_id == workflow_id

    @pytest.mark.asyncio
    async def test_an_ownerless_workflow_leaves_the_recorder_to_derive_the_agent(self, monkeypatch):
        monkeypatch.setattr(test_suite_module, "WorkflowEngine", EngineStub)

        async def _accept(*_args, **_kwargs):
            return None

        service = _service()
        spy = EvaluatorSpy()
        service.evaluators = spy
        service.run_repo = SimpleNamespace(update=_accept)
        service.result_repo = SimpleNamespace(create=_accept)
        case = SimpleNamespace(
            id=uuid4(),
            source_conversation_id=None,
            turn_index=0,
            created_at=0,
            input_data={"message": "hello"},
            expected_output=None,
        )
        monkeypatch.setattr(service, "list_cases_for_suite", lambda _suite_id: _async([case]))
        suite = SimpleNamespace(id=uuid4(), default_input_metadata=None)
        run = SimpleNamespace(id=uuid4(), status="pending", techniques=["contains"], summary_metrics=None)

        await service._execute_run_inner(suite, self._workflow(uuid4(), None), run)

        assert spy.usage_refs[0].agent_id is None
