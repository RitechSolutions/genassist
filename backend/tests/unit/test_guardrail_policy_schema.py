import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentUpdate
from app.schemas.agent_security_settings import (
    AgentSecuritySettingsCreate,
    AgentSecuritySettingsRead,
    AgentSecuritySettingsUpdate,
)


def _saved_security_settings(payload: dict) -> dict:
    changes = AgentUpdate.model_validate(payload).model_dump(exclude_unset=True)
    return AgentSecuritySettingsUpdate(**changes["security_settings"]).model_dump(exclude_unset=True)


@pytest.mark.parametrize(
    "policy",
    [
        {"mode": "block", "prompt_attack": "medium"},
        {"mode": "detect", "harmful_content": {"hate": "low"}},
        {"mode": "block", "denied_topics": [{"name": "Legal advice", "definition": "Court fines"}]},
        {"mode": "detect", "untrusted_content": "flag"},
    ],
)
def test_judge_backed_checks_with_mode_on_need_a_judge(policy):
    with pytest.raises(ValidationError, match="Pick a judge model"):
        AgentUpdate.model_validate({"security_settings": {"guardrails": policy}})
    with pytest.raises(ValidationError, match="Pick a judge model"):
        AgentSecuritySettingsCreate(guardrails=policy)


def test_mode_off_and_rules_only_policies_save_without_a_judge():
    off = _saved_security_settings({"security_settings": {"guardrails": {"mode": "off", "prompt_attack": "high"}}})
    assert off["guardrails"] == {"mode": "off", "prompt_attack": "high"}

    words = _saved_security_settings({"security_settings": {"guardrails": {"mode": "block", "blocked_words": [" rival "]}}})
    assert words["guardrails"]["blocked_words"] == ["rival"]


def test_saved_policy_is_jsonb_safe_with_a_string_judge_id():
    judge = uuid4()
    saved = _saved_security_settings(
        {"security_settings": {"guardrails": {"mode": "block", "prompt_attack": "medium", "judge_provider_id": str(judge)}}}
    )
    assert saved["guardrails"]["judge_provider_id"] == str(judge)
    assert json.loads(json.dumps(saved))["guardrails"]["judge_provider_id"] == str(judge)


def test_blank_judge_and_blank_blocked_message_fall_back():
    saved = _saved_security_settings(
        {"security_settings": {"guardrails": {"mode": "detect", "judge_provider_id": "", "blocked_message": "   "}}}
    )
    assert saved["guardrails"]["judge_provider_id"] is None
    assert saved["guardrails"]["blocked_message"] == "Sorry, I can't help with that."


def test_null_guardrails_clears_the_policy_and_other_saves_leave_it_alone():
    assert _saved_security_settings({"security_settings": {"guardrails": None}}) == {"guardrails": None}
    assert "guardrails" not in _saved_security_settings({"security_settings": {"token_based_auth": True}})


def test_read_accepts_a_stored_policy_without_a_judge():
    read = AgentSecuritySettingsRead.model_validate(
        {"id": uuid4(), "agent_id": uuid4(), "guardrails": {"mode": "block", "prompt_attack": "high"}}
    )
    assert read.guardrails.mode == "block"
    assert read.guardrails.judge_provider_id is None
    assert AgentSecuritySettingsRead.model_validate({"id": uuid4(), "agent_id": uuid4()}).guardrails is None
