"""Persisted shapes for sub-agent delegation frames"""

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SubAgentMode = Literal["single_turn", "task", "chat"]
SubAgentAgentType = Literal["ToolSelector", "ReActAgent", "ReActAgentLC"]

FRAME_VERSION = 1
FRAME_TTL_HOURS = 24

SUB_AGENT_RESUME_KEY = "__sub_agent_resume"
# Rides inside the frame's free-form request_context, so ParentResume keeps its schema
# and an older pod can still resume a frame written by a newer one
SUB_AGENT_DIAGNOSTICS_KEY = "__prompt_caching_diagnostics"

MAX_TASK_CHARS = 4000
MAX_USER_PROMPT_CHARS = 4000

MIN_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 300.0
DEFAULT_CHILD_TIMEOUT_SECONDS = 120.0


def clamp_child_timeout_seconds(value: Any) -> float:
    """Read a child timeout for the parent: return a finite float in range, or the default"""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return DEFAULT_CHILD_TIMEOUT_SECONDS
    if not isfinite(seconds) or not (MIN_TIMEOUT_SECONDS <= seconds <= MAX_TIMEOUT_SECONDS):
        return DEFAULT_CHILD_TIMEOUT_SECONDS
    return seconds


class SubAgentConfig(BaseModel):

    model_config = ConfigDict(extra="ignore")

    providerId: Optional[str] = None
    description: Optional[str] = None
    mode: SubAgentMode = "single_turn"
    type: SubAgentAgentType = "ToolSelector"
    timeoutSeconds: float = DEFAULT_CHILD_TIMEOUT_SECONDS

    @field_validator("timeoutSeconds", mode="before")
    @classmethod
    def _finite_in_range(cls, value: Any) -> float:
        try:
            seconds = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("timeoutSeconds must be a number") from exc
        if not isfinite(seconds):
            raise ValueError("timeoutSeconds must be a finite number")
        if not (MIN_TIMEOUT_SECONDS <= seconds <= MAX_TIMEOUT_SECONDS):
            raise ValueError("timeoutSeconds must be between 5 and 300")
        return seconds


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expiry_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=FRAME_TTL_HOURS)).isoformat()


class ParentResume(BaseModel):
    """Snapshot the parent agent needs to continue after a child hands back"""

    model_config = ConfigDict(extra="forbid")

    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    node_execution_status: Dict[str, Any] = Field(default_factory=dict)
    request_context: Dict[str, Any] = Field(default_factory=dict)
    user_prompt: str = Field(default="", max_length=MAX_USER_PROMPT_CHARS)
    completed_count: int = 0
    accumulated_steps: List[Any] = Field(default_factory=list)
    accumulated_tools_used: List[Any] = Field(default_factory=list)


class SubAgentFrame(BaseModel):
    """One paused parent→child delegation on the stack"""

    model_config = ConfigDict(extra="forbid")

    version: int = FRAME_VERSION
    child_node_id: str
    parent_node_id: str
    workflow_id: str
    invocation_id: str
    mode: Literal["task", "chat"]
    task: str = Field(default="", max_length=MAX_TASK_CHARS)
    inherit_pii: bool = False
    created_at: str = Field(default_factory=_now_iso)
    expires_at: str = Field(default_factory=_expiry_iso)
    workflow_fingerprint: str = ""
    parent_resume: ParentResume = Field(default_factory=ParentResume)

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        try:
            return now >= datetime.fromisoformat(self.expires_at)
        except (ValueError, TypeError):
            return True


class SubAgentStack(BaseModel):
    """The ordered frame stack for one agent on one root thread"""

    model_config = ConfigDict(extra="forbid")

    version: int = FRAME_VERSION
    agent_id: str
    frames: List[SubAgentFrame] = Field(default_factory=list)

    def top(self) -> SubAgentFrame | None:
        return self.frames[-1] if self.frames else None
