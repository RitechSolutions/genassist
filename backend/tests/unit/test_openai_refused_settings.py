"""A setting an OpenAI model refuses is replaced and the call repeated"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from app.modules.workflow.llm import openai_refused_settings
from app.modules.workflow.llm.provider import build_chat_model
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS
from app.services.app_settings import AppSettingsService
from app.services.llm_providers import LlmProviderService

_MODEL = "gpt-6.1-sol"
_DEFAULT_FORM_VALUES = {"reasoning_effort": "none", "temperature": 0.7}

_REFUSED_EFFORT = {
    "message": (
        "Unsupported value: 'reasoning_effort' does not support 'none' with this model. "
        "Supported values are: 'low', 'medium', 'high', and 'xhigh'."
    ),
    "type": "invalid_request_error",
    "param": "reasoning_effort",
    "code": "unsupported_value",
}
_REFUSED_TEMPERATURE = {
    "message": (
        "Unsupported value: 'temperature' does not support 0.7 with this model. "
        "Only the default (1) value is supported."
    ),
    "type": "invalid_request_error",
    "param": "temperature",
    "code": "unsupported_value",
}
_REFUSED_EXTRA_HIGH = {
    "message": (
        "Unsupported value: 'reasoning_effort' does not support 'xhigh' with this model. "
        "Supported values are: 'minimal', 'low', 'medium', and 'high'."
    ),
    "type": "invalid_request_error",
    "param": "reasoning_effort",
    "code": "unsupported_value",
}
_REFUSED_HIGH = {
    **_REFUSED_EXTRA_HIGH,
    "message": "Unsupported value: 'reasoning_effort' does not support 'high' with this model.",
}
_TOO_LONG = {
    "message": "This model's maximum context length is 8192 tokens.",
    "type": "invalid_request_error",
    "param": "messages",
    "code": "context_length_exceeded",
}


def _has_custom_temperature(body):
    return body.get("temperature") not in (None, 1)


def _reasoning_only_model(body):
    """Always reasons and takes only its default temperature."""
    if body.get("reasoning_effort") == "none":
        return _REFUSED_EFFORT
    if _has_custom_temperature(body):
        return _REFUSED_TEMPERATURE
    return None


def _reasoning_only_model_naming_temperature_first(body):
    if _has_custom_temperature(body):
        return _REFUSED_TEMPERATURE
    if body.get("reasoning_effort") == "none":
        return _REFUSED_EFFORT
    return None


def _model_with_optional_reasoning(body):
    """Takes a temperature only while it is not reasoning."""
    is_reasoning = body.get("reasoning_effort") != "none"
    if is_reasoning and _has_custom_temperature(body):
        return _REFUSED_TEMPERATURE
    return None


def _model_without_extra_high(body):
    """Takes every effort up to High."""
    if body.get("reasoning_effort") == "xhigh":
        return _REFUSED_EXTRA_HIGH
    return None


def _model_without_extra_high_or_temperature(body):
    return _model_without_extra_high(body) or (_REFUSED_TEMPERATURE if _has_custom_temperature(body) else None)


def _model_without_high_efforts(body):
    """Refuses both High and Extra High."""
    if body.get("reasoning_effort") == "high":
        return _REFUSED_HIGH
    return _model_without_extra_high(body)


def _answer(body):
    message = {"role": "assistant", "content": "pong"}
    choice = {"index": 0, "message": message, "finish_reason": "stop"}
    usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
    completion = {"id": "c-1", "object": "chat.completion", "created": 0, "model": body["model"]}
    return httpx.Response(200, json={**completion, "choices": [choice], "usage": usage})


def _streamed_answer(body):
    chunk = {"id": "c-1", "object": "chat.completion.chunk", "created": 0, "model": body["model"]}
    said = {**chunk, "choices": [{"index": 0, "delta": {"role": "assistant", "content": "pong"}}]}
    done = {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    events = "".join(f"data: {json.dumps(event)}\n\n" for event in (said, done)) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=events.encode())


class _FakeOpenAI:
    """Answers like the OpenAI API and keeps every request body it was sent."""

    def __init__(self, refusal_for=lambda body: None):
        self._refusal_for = refusal_for
        self.bodies = []

    def _respond(self, request):
        body = json.loads(request.content)
        self.bodies.append(body)
        refusal = self._refusal_for(body)
        if refusal:
            return httpx.Response(400, json={"error": refusal})
        return _streamed_answer(body) if body.get("stream") else _answer(body)

    async def _respond_after_a_pause(self, request):
        """Lets calls started together reach the API before any of them is answered."""
        await asyncio.sleep(0)
        return self._respond(request)

    def connection(self, **settings):
        clients = {
            "http_client": httpx.Client(transport=httpx.MockTransport(self._respond)),
            "http_async_client": httpx.AsyncClient(transport=httpx.MockTransport(self._respond_after_a_pause)),
        }
        return {"api_key": "k", **clients, **settings}

    async def model(self, model_name=_MODEL, **settings):
        return await build_chat_model("openai", self.connection(**settings), model_name)

    @property
    def sent_settings(self):
        return [(body.get("reasoning_effort"), body.get("temperature")) for body in self.bodies]


async def _ainvoke(llm):
    return (await llm.ainvoke("ping")).content


async def _invoke(llm):
    return llm.invoke("ping").content


async def _astream(llm):
    return "".join([chunk.content async for chunk in llm.astream("ping")])


async def _stream(llm):
    return "".join(chunk.content for chunk in llm.stream("ping"))


@pytest.fixture(autouse=True)
def _nothing_remembered():
    openai_refused_settings._refusals.clear()
    with patch.dict("os.environ"):
        yield
    openai_refused_settings._refusals.clear()


@pytest.mark.asyncio
class TestDefaultFormValuesOnAReasoningOnlyModel:
    @pytest.mark.parametrize("call", [_ainvoke, _invoke, _astream, _stream])
    async def test_every_way_of_calling_gets_an_answer(self, call):
        openai_api = _FakeOpenAI(_reasoning_only_model)
        llm = await openai_api.model(**_DEFAULT_FORM_VALUES)

        assert await call(llm) == "pong"
        assert openai_api.sent_settings == [("none", 0.7), ("low", 0.7), ("low", None)]

    async def test_the_replaced_settings_are_reported(self):
        llm = await _FakeOpenAI(_reasoning_only_model).model(**_DEFAULT_FORM_VALUES)
        await _ainvoke(llm)

        assert llm.adjusted_settings == {"reasoning_effort": "low", "temperature": None}

    async def test_the_next_model_starts_with_the_accepted_values(self):
        openai_api = _FakeOpenAI(_reasoning_only_model)
        await _ainvoke(await openai_api.model(**_DEFAULT_FORM_VALUES))
        refusals_before = len(openai_api.bodies) - 1

        later_model = await openai_api.model(**_DEFAULT_FORM_VALUES)
        await _ainvoke(later_model)

        assert refusals_before == 2
        assert openai_api.sent_settings[-2:] == [("low", None), ("low", None)]
        assert later_model.adjusted_settings == {"reasoning_effort": "low", "temperature": None}

    async def test_the_first_call_works_whichever_setting_is_refused_first(self):
        openai_api = _FakeOpenAI(_reasoning_only_model_naming_temperature_first)

        assert await _ainvoke(await openai_api.model(**_DEFAULT_FORM_VALUES)) == "pong"
        assert openai_api.sent_settings == [("none", 0.7), ("none", None), ("low", None)]

    async def test_a_learned_refusal_is_logged_once(self):
        openai_api = _FakeOpenAI(_reasoning_only_model)

        with patch.object(openai_refused_settings.logger, "info") as log:
            for _ in range(2):
                await _ainvoke(await openai_api.model(**_DEFAULT_FORM_VALUES))

        assert [call.args[2] for call in log.call_args_list] == ["reasoning_effort", "temperature"]

    async def test_calls_running_at_once_all_get_an_answer(self):
        openai_api = _FakeOpenAI(_reasoning_only_model)
        llm = await openai_api.model(**_DEFAULT_FORM_VALUES)

        answers = await asyncio.gather(*(_ainvoke(llm) for _ in range(4)))

        assert answers == ["pong"] * 4
        assert openai_api.sent_settings.count(("none", 0.7)) == 4

    async def test_a_temperature_bound_for_one_call_is_dropped_too(self):
        openai_api = _FakeOpenAI(_reasoning_only_model)
        llm = await openai_api.model(reasoning_effort="low")

        answer = await llm.bind(temperature=0, max_tokens=10).ainvoke("ping")

        assert answer.content == "pong"
        assert openai_api.sent_settings == [("low", 0), ("low", None)]
        assert llm.adjusted_settings == {}


@pytest.mark.asyncio
class TestExtraHighOnAModelThatRefusesIt:
    @pytest.mark.parametrize("call", [_ainvoke, _invoke, _astream, _stream])
    async def test_every_way_of_calling_gets_an_answer_with_high(self, call):
        openai_api = _FakeOpenAI(_model_without_extra_high)
        llm = await openai_api.model(reasoning_effort="xhigh")

        assert await call(llm) == "pong"
        assert openai_api.sent_settings == [("xhigh", None), ("high", None)]
        assert llm.adjusted_settings == {"reasoning_effort": "high"}

    async def test_the_next_model_starts_with_high(self):
        openai_api = _FakeOpenAI(_model_without_extra_high)
        await _ainvoke(await openai_api.model(reasoning_effort="xhigh"))

        await _ainvoke(await openai_api.model(reasoning_effort="xhigh"))

        assert openai_api.sent_settings == [("xhigh", None), ("high", None), ("high", None)]

    async def test_a_refused_temperature_is_left_out_as_well(self):
        openai_api = _FakeOpenAI(_model_without_extra_high_or_temperature)
        llm = await openai_api.model(reasoning_effort="xhigh", temperature=0.7)

        assert await _ainvoke(llm) == "pong"
        assert openai_api.sent_settings == [("xhigh", 0.7), ("high", 0.7), ("high", None)]
        assert llm.adjusted_settings == {"reasoning_effort": "high", "temperature": None}

    async def test_a_model_that_also_refuses_high_fails_with_its_own_message(self):
        openai_api = _FakeOpenAI(_model_without_high_efforts)
        llm = await openai_api.model(reasoning_effort="xhigh")

        with pytest.raises(openai.BadRequestError, match="does not support 'high'"):
            await _ainvoke(llm)
        assert openai_api.sent_settings == [("xhigh", None), ("high", None)]


@pytest.mark.asyncio
class TestSettingsTheModelAccepts:
    async def test_an_accepted_extra_high_is_sent_as_configured(self):
        openai_api = _FakeOpenAI()
        llm = await openai_api.model(reasoning_effort="xhigh")
        await _ainvoke(llm)

        assert openai_api.sent_settings == [("xhigh", None)]
        assert llm.adjusted_settings == {}

    async def test_accepted_settings_are_sent_as_configured(self):
        openai_api = _FakeOpenAI()
        llm = await openai_api.model(**_DEFAULT_FORM_VALUES)
        await _ainvoke(llm)

        assert openai_api.sent_settings == [("none", 0.7)]
        assert llm.adjusted_settings == {}

    async def test_a_temperature_refused_while_reasoning_is_kept_without_reasoning(self):
        openai_api = _FakeOpenAI(_model_with_optional_reasoning)
        await _ainvoke(await openai_api.model(reasoning_effort="low", temperature=0.7))

        await _ainvoke(await openai_api.model(reasoning_effort="none", temperature=0.3))

        assert openai_api.sent_settings == [("low", 0.7), ("low", None), ("none", 0.3)]

    async def test_the_default_temperature_is_still_sent_after_another_was_refused(self):
        openai_api = _FakeOpenAI(_reasoning_only_model)
        await _ainvoke(await openai_api.model(reasoning_effort="low", temperature=0.7))

        llm = await openai_api.model(reasoning_effort="low", temperature=1)
        await _ainvoke(llm)

        assert openai_api.sent_settings[-1] == ("low", 1)
        assert llm.adjusted_settings == {}

    async def test_a_refusal_from_another_endpoint_changes_nothing(self):
        other_endpoint = _FakeOpenAI(_reasoning_only_model)
        await _ainvoke(await other_endpoint.model(base_url="https://llm.acme.example/v1", **_DEFAULT_FORM_VALUES))

        openai_api = _FakeOpenAI()
        await _ainvoke(await openai_api.model(**_DEFAULT_FORM_VALUES))

        assert openai_api.sent_settings == [("none", 0.7)]


@pytest.mark.asyncio
class TestRefusalsThatAreNotReplaced:
    async def test_another_bad_request_is_raised_as_it_is(self):
        openai_api = _FakeOpenAI(lambda body: _TOO_LONG)
        llm = await openai_api.model(**_DEFAULT_FORM_VALUES)

        with pytest.raises(openai.BadRequestError, match="maximum context length"):
            await _ainvoke(llm)
        assert len(openai_api.bodies) == 1

    async def test_a_refused_high_is_raised_as_it_is(self):
        openai_api = _FakeOpenAI(_model_without_high_efforts)
        llm = await openai_api.model(reasoning_effort="high")

        with pytest.raises(openai.BadRequestError, match="does not support 'high'"):
            await _ainvoke(llm)
        assert openai_api.sent_settings == [("high", None)]
        assert not openai_refused_settings._refusals

    async def test_a_full_memory_drops_only_its_oldest_refusal(self):
        oldest, older = (None, "gpt-a", "temperature", "low"), (None, "gpt-b", "temperature", "low")
        openai_refused_settings._refusals.update({oldest: None, older: None})
        openai_api = _FakeOpenAI(_reasoning_only_model)

        with patch.object(openai_refused_settings, "_MAX_REMEMBERED", 3):
            answer = await _ainvoke(await openai_api.model(**_DEFAULT_FORM_VALUES))

        assert answer == "pong"
        assert openai_api.sent_settings == [("none", 0.7), ("low", 0.7), ("low", None)]
        assert oldest not in openai_refused_settings._refusals
        assert len(openai_refused_settings._refusals) == 3


@pytest.mark.asyncio
class TestConnectionTest:
    @pytest.fixture
    def service(self):
        return LlmProviderService(
            repository=AsyncMock(spec=LlmProviderRepository),
            app_settings_service=AsyncMock(spec=AppSettingsService),
        )

    async def _test(self, service, refusal_for, form_values=_DEFAULT_FORM_VALUES):
        connection = _FakeOpenAI(refusal_for).connection(model=_MODEL, **form_values)
        return await service.test_connection("openai", connection)

    async def test_replaced_settings_come_back_with_a_note(self, service):
        result = await self._test(service, _reasoning_only_model)

        assert result == {
            "success": True,
            "message": (
                "Connection successful. "
                "Reasoning Effort None is not supported by this model, so Low is used. "
                "This model only accepts its default temperature, so Temperature is left empty."
            ),
            "adjusted_settings": {"reasoning_effort": "low", "temperature": None},
        }

    async def test_a_replaced_extra_high_comes_back_with_its_note(self, service):
        result = await self._test(service, _model_without_extra_high, {"reasoning_effort": "xhigh"})

        assert result == {
            "success": True,
            "message": (
                "Connection successful. "
                "Reasoning Effort Extra High is not supported by this model, so High is used."
            ),
            "adjusted_settings": {"reasoning_effort": "high"},
        }

    async def test_accepted_settings_give_the_plain_result(self, service):
        result = await self._test(service, lambda body: None)

        assert result == {"success": True, "message": "Connection successful."}


def test_extra_high_reasoning_effort_can_be_chosen():
    fields = {field.name: field for field in LLM_FORM_SCHEMAS["openai"].fields}
    efforts = [option["value"] for option in fields["reasoning_effort"].options]

    assert efforts == ["none", "low", "medium", "high", "xhigh"]
