"""Keeps OpenAI calls working when a model refuses a provider setting.

OpenAI names the refused setting in its 400 response, before any output is sent.
The refusal is remembered for the process, and the setting is replaced in every
later request to the same model on the same endpoint.
"""

from __future__ import annotations

import logging
import threading
from contextvars import ContextVar
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple

import openai
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

REASONING_EFFORT = "reasoning_effort"
TEMPERATURE = "temperature"
NO_REASONING = "none"
FALLBACK_REASONING_EFFORT = "low"
DEFAULT_TEMPERATURE = 1

_UNSUPPORTED_VALUE = "unsupported_value"
_MAX_REMEMBERED = 1000
# A call can be refused once for each replaceable setting before it goes through.
_MAX_REPEATS = 2

_ADJUSTMENT_NOTES = {
    REASONING_EFFORT: "Reasoning Effort None is not supported by this model, so Low is used.",
    TEMPERATURE: "This model only accepts its default temperature, so Temperature is left empty.",
}

# (endpoint, model)
Scope = Tuple[Optional[str], str]

RefusalKey = Tuple[Optional[str], str, str, Optional[str]]

# (endpoint, model, setting, reasoning effort sent) of every refusal a later request can avoid, oldest first.
_refusals: Dict[RefusalKey, None] = {}
_refusals_lock = threading.Lock()

# Both settings as carried by the request last built in this task or thread.
_sent_settings: ContextVar[Dict[str, Any]] = ContextVar("openai_sent_settings")


def refused_setting(error: openai.BadRequestError) -> Optional[str]:
    """The setting OpenAI refused, when it is one this module can replace."""
    is_unsupported_value = getattr(error, "code", None) == _UNSUPPORTED_VALUE
    setting = getattr(error, "param", None)
    if is_unsupported_value and setting in _ADJUSTMENT_NOTES:
        return setting
    return None


def adjustment_notes(adjusted_settings: Dict[str, Any]) -> List[str]:
    """One sentence per replaced setting, for the connection test result."""
    return [_ADJUSTMENT_NOTES[setting] for setting in adjusted_settings if setting in _ADJUSTMENT_NOTES]


def _is_refused(scope: Scope, setting: str, effort: Optional[str]) -> bool:
    return (*scope, setting, effort) in _refusals


def _replace_refused(scope: Scope, settings: Dict[str, Any]) -> None:
    """Replace, in place, the settings this model is known to refuse."""
    asked_effort = settings.get(REASONING_EFFORT)
    if asked_effort == NO_REASONING and _is_refused(scope, REASONING_EFFORT, NO_REASONING):
        settings[REASONING_EFFORT] = FALLBACK_REASONING_EFFORT

    # A temperature refused without reasoning is refused with it too.
    efforts_to_check = {asked_effort, settings.get(REASONING_EFFORT)}
    temperature_refused = any(_is_refused(scope, TEMPERATURE, effort) for effort in efforts_to_check)
    has_custom_temperature = settings.get(TEMPERATURE) not in (None, DEFAULT_TEMPERATURE)
    if has_custom_temperature and temperature_refused:
        del settings[TEMPERATURE]


def _remember(scope: Scope, setting: str, sent: Dict[str, Any]) -> None:
    """Keep a refusal that a later request can avoid."""
    effort = sent.get(REASONING_EFFORT)
    is_replaceable = setting == TEMPERATURE or effort == NO_REASONING
    if not is_replaceable:
        return
    key = (*scope, setting, effort)
    with _refusals_lock:
        if key in _refusals:
            return
        if len(_refusals) >= _MAX_REMEMBERED:
            del _refusals[next(iter(_refusals))]
        _refusals[key] = None
    logger.info(
        "OpenAI model %s refused %s=%r; later requests to it replace this setting until the process restarts",
        scope[1],
        setting,
        sent.get(setting),
    )


class RefusalAdjustingChatOpenAI(ChatOpenAI):
    """ChatOpenAI that replaces a setting in its requests once the model has refused it."""

    @property
    def adjusted_settings(self) -> Dict[str, Any]:
        """Provider settings the model refuses, with the value sent instead."""
        configured = {REASONING_EFFORT: self.reasoning_effort, TEMPERATURE: self.temperature}
        sent = dict(configured)
        _replace_refused(self._refusal_scope, sent)
        return {setting: sent.get(setting) for setting, value in configured.items() if sent.get(setting) != value}

    @property
    def _refusal_scope(self) -> Scope:
        return (self.openai_api_base, self.model_name)

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        _replace_refused(self._refusal_scope, payload)
        _sent_settings.set({setting: payload.get(setting) for setting in _ADJUSTMENT_NOTES})
        return payload

    def _learned_from(self, refusal: openai.BadRequestError) -> bool:
        """Remember the refusal. True when the same call would now be sent differently."""
        setting = refused_setting(refusal)
        sent = _sent_settings.get(None)
        if setting is None or sent is None:
            return False
        _remember(self._refusal_scope, setting, sent)
        accepted = dict(sent)
        _replace_refused(self._refusal_scope, accepted)
        return accepted != sent

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        for _ in range(_MAX_REPEATS):
            try:
                return super()._generate(messages, stop, run_manager, **kwargs)
            except openai.BadRequestError as refusal:
                if not self._learned_from(refusal):
                    raise
        return super()._generate(messages, stop, run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        for _ in range(_MAX_REPEATS):
            try:
                return await super()._agenerate(messages, stop, run_manager, **kwargs)
            except openai.BadRequestError as refusal:
                if not self._learned_from(refusal):
                    raise
        return await super()._agenerate(messages, stop, run_manager, **kwargs)

    def _stream(self, *args: Any, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        for _ in range(_MAX_REPEATS):
            try:
                yield from super()._stream(*args, **kwargs)
                return
            except openai.BadRequestError as refusal:
                if not self._learned_from(refusal):
                    raise
        yield from super()._stream(*args, **kwargs)

    async def _astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
        for _ in range(_MAX_REPEATS):
            try:
                async for chunk in super()._astream(*args, **kwargs):
                    yield chunk
                return
            except openai.BadRequestError as refusal:
                if not self._learned_from(refusal):
                    raise
        async for chunk in super()._astream(*args, **kwargs):
            yield chunk
