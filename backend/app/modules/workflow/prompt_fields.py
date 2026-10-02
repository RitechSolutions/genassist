"""Prompt fields the Prompt Editor may open, and what each one supports"""

from dataclasses import dataclass
from typing import Dict, Literal, Optional, Tuple

PromptRole = Literal[
    "system",
    "user",
    "router_instructions",
    "router_question",
    "judge_suffix",
    "sql_system",
]


@dataclass(frozen=True)
class PromptFieldSpec:
    """One editable prompt field.

    ``label`` - shown in editor header, copied from node dialog.
    ``inline_check`` - marks fields the prompt check can test (system-role only).
    If False, ``unsupported_reason`` is required and shown to user.
    """

    field: str
    role: PromptRole
    label: str
    inline_check: bool
    unsupported_reason: Optional[str] = None


_ISOLATED = (
    "The isolated check runs the text as a system prompt, "
    "which is not how this field is used at run time."
)

# Router becomes the system message, so can't use a generic reason 
# Check can't reproduce the full call either
_ROUTER_ISOLATED = (
    "The isolated check cannot reproduce the router's routing prompt, "
    "true/false output contract, and constrained response."
)

_SYSTEM = PromptFieldSpec("systemPrompt", "system", "System Prompt", inline_check=True)
_USER = PromptFieldSpec("userPrompt", "user", "User Prompt", False, _ISOLATED)
_ROUTER_INSTR = PromptFieldSpec(
    "systemPrompt", "router_instructions", "System Prompt", False, _ROUTER_ISOLATED
)
_ROUTER_QUESTION = PromptFieldSpec("smartPrompt", "router_question", "Routing prompt", False, _ISOLATED)
_SQL_SYSTEM = PromptFieldSpec("systemPrompt", "sql_system", "System Prompt", False, _ISOLATED)
_JUDGE_SUFFIX = PromptFieldSpec(
    "llm_judge_system_prompt_suffix", "judge_suffix", "Additional judge instructions", False, _ISOLATED
)

PROMPT_FIELDS: Dict[str, Dict[str, PromptFieldSpec]] = {
    "agentNode": {"systemPrompt": _SYSTEM, "userPrompt": _USER},
    "llmModelNode": {"systemPrompt": _SYSTEM, "userPrompt": _USER},
    "subAgentNode": {"systemPrompt": _SYSTEM},
    "routerNode": {"systemPrompt": _ROUTER_INSTR, "smartPrompt": _ROUTER_QUESTION},
    "sqlNode": {"systemPrompt": _SQL_SYSTEM},
    "guardrailProvenanceNode": {"llm_judge_system_prompt_suffix": _JUDGE_SUFFIX},
}

# Old dialogs sent wrong node IDs, so every Agent/LLM node 
# shared the same history per field.
LEGACY_SHARED_NODE_IDS: Dict[str, Tuple[str, ...]] = {
    "agent-config": ("agentNode", "llmModelNode"),
    "sub-agent-config": ("subAgentNode",),
}

LEGACY_BUCKET_FOR_NODE_TYPE: Dict[str, str] = {
    node_type: bucket
    for bucket, node_types in LEGACY_SHARED_NODE_IDS.items()
    for node_type in node_types
}


def get_spec(node_type: str, prompt_field: str) -> Optional[PromptFieldSpec]:
    return PROMPT_FIELDS.get(node_type, {}).get(prompt_field)
