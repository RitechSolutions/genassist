"""Which request parameters a given model accepts.

Providers keep tightening what newer models take: recent Claude models reject
`temperature`, and only reasoning OpenAI models take `reasoning_effort`. These
helpers read the model id so the provider factory and the nodes can leave out
what the model would reject with a 400.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

SAMPLING_PARAMS = ("temperature", "top_p", "top_k")

# Matches current Claude ids in any provider's spelling: "claude-sonnet-5-5",
# "anthropic.claude-opus-4-7-v1:0", "anthropic/claude-sonnet-4.6". The minor
# version is one or two digits so a date suffix ("claude-opus-4-20250514") is not
# read as one. Claude 3 ids ("claude-3-5-sonnet-...") put the number first and
# don't match, which is right: they take every old parameter.
_CLAUDE_RE = re.compile(
    r"claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:[-.](\d{1,2}))?(?!\d)"
)


def _claude_version(model_name: Optional[str]) -> Optional[tuple[str, int, int]]:
    match = _CLAUDE_RE.search((model_name or "").lower())
    if not match:
        return None
    family, major, minor = match.groups()
    return family, int(major), int(minor or 0)


def claude_rejects_sampling(model_name: Optional[str]) -> bool:
    """True for Claude models that return a 400 when temperature/top_p/top_k is sent.

    That is every Claude 5 model, and Opus 4.7 / 4.8.
    """
    version = _claude_version(model_name)
    if version is None:
        return False
    family, major, minor = version
    return major >= 5 or (family == "opus" and major == 4 and minor >= 7)


def claude_uses_adaptive_thinking(model_name: Optional[str]) -> bool:
    """True for Claude 4.6 and newer, where thinking is `{"type": "adaptive"}`.

    `budget_tokens` is rejected on the newest of these and deprecated on 4.6.
    """
    version = _claude_version(model_name)
    if version is None:
        return False
    _, major, minor = version
    return major >= 5 or (major == 4 and minor >= 6)


def _openai_base_name(model_name: Optional[str]) -> str:
    name = (model_name or "").lower()
    # Fine-tuned ids look like "ft:gpt-4o-mini:org::id".
    if name.startswith("ft:"):
        name = name[3:]
    # OpenRouter-style ids carry a vendor prefix: "openai/gpt-5.1".
    return name.rsplit("/", 1)[-1]


def openai_supports_reasoning_effort(model_name: Optional[str]) -> bool:
    """True for OpenAI reasoning models (o-series and the GPT-5 family).

    Other models (gpt-4o, gpt-3.5, ...) reject `reasoning_effort` with a 400.
    """
    name = _openai_base_name(model_name)
    if re.match(r"o\d", name):
        return True
    match = re.match(r"gpt-(\d+)", name)
    return bool(match) and int(match.group(1)) >= 5 and "chat" not in name


def openai_accepts_reasoning_none(model_name: Optional[str]) -> bool:
    """True for GPT-5.1 and newer, which take `reasoning_effort="none"`.

    gpt-5 / gpt-5-mini / gpt-5-nano and the o-series don't; nor do the pro and
    codex variants, which have their own fixed effort ranges.
    """
    name = _openai_base_name(model_name)
    if any(tag in name for tag in ("-pro", "-codex", "-chat")):
        return False
    match = re.match(r"gpt-(\d+)(?:\.(\d+))?", name)
    if not match:
        return False
    major, minor = int(match.group(1)), int(match.group(2) or 0)
    return major > 5 or (major == 5 and minor >= 1)


def _model_name_of(llm: Any) -> Optional[str]:
    for attr in ("model", "model_name", "model_id"):
        value = getattr(llm, attr, None)
        if isinstance(value, str) and value:
            return value
    return None


def deterministic_kwargs(llm: Any) -> Dict[str, Any]:
    """`bind()` kwargs that ask for a deterministic answer, when the model allows it.

    Nodes that classify or route bind `temperature=0`. Models that reject sampling
    parameters get nothing instead of a 400.
    """
    if claude_rejects_sampling(_model_name_of(llm)):
        return {}
    return {"temperature": 0}
