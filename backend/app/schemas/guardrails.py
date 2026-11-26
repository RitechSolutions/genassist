from datetime import datetime
from typing import Annotated, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_serializer, field_validator

Sensitivity = Literal["off", "low", "medium", "high"]
DEFAULT_BLOCKED_MESSAGE = "Sorry, I can't help with that."


class HarmfulContent(BaseModel):
    hate: Sensitivity = "off"
    insults: Sensitivity = "off"
    sexual: Sensitivity = "off"
    violence: Sensitivity = "off"
    self_harm: Sensitivity = "off"
    misconduct: Sensitivity = "off"


class DeniedTopic(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    definition: str = Field(..., min_length=1, max_length=300)
    examples: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=3
    )


class GuardrailChecks(BaseModel):
    judge_provider_id: Optional[UUID] = None
    prompt_attack: Sensitivity = "off"
    harmful_content: HarmfulContent = Field(default_factory=HarmfulContent)
    denied_topics: list[DeniedTopic] = Field(default_factory=list, max_length=20)
    blocked_words: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=200
    )
    previous_reply_context: bool = False
    blocked_message: str = Field(DEFAULT_BLOCKED_MESSAGE, max_length=500)

    @field_validator("judge_provider_id", mode="before")
    @classmethod
    def _blank_judge_is_none(cls, value):
        return None if value == "" else value

    @field_validator("blocked_message", mode="before")
    @classmethod
    def _blank_message_is_default(cls, value):
        return DEFAULT_BLOCKED_MESSAGE if value is None or not str(value).strip() else value

    @field_serializer("judge_provider_id")
    def _judge_as_str(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value is not None else None

    def uses_judge(self) -> bool:
        return (
            self.prompt_attack != "off"
            or any(level != "off" for level in self.harmful_content.model_dump().values())
            or bool(self.denied_topics)
        )


class GuardrailPolicy(GuardrailChecks):
    mode: Literal["off", "detect", "block"] = "off"
    check_replies: bool = False
    untrusted_content: Literal["off", "flag", "block"] = "off"

    def needs_judge(self) -> bool:
        return self.mode != "off" and (self.uses_judge() or self.untrusted_content != "off")


def require_judge(policy: Optional[GuardrailPolicy]) -> Optional[GuardrailPolicy]:
    if policy is not None and policy.needs_judge() and policy.judge_provider_id is None:
        raise ValueError("Pick a judge model to run prompt attack, harmful content, topic or tool result checks.")
    return policy


class GuardrailVerdict(BaseModel):
    stage: str
    check_type: str
    category: Optional[str] = None
    detector: str
    score: Optional[float] = None
    mode: str
    action: str
    source: Optional[str] = None


class GuardrailCheckRequest(BaseModel):
    policy: GuardrailPolicy
    text: str = Field(..., min_length=1, max_length=20000)
    previous_reply: Optional[str] = Field(None, max_length=20000)


class GuardrailCheckResponse(BaseModel):
    blocked: bool
    verdicts: list[GuardrailVerdict]


class GuardrailEventRead(GuardrailVerdict):
    id: UUID
    transcript_message_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
