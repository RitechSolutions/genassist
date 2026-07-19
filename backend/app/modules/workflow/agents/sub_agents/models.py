"""Persisted shapes for sub-agent delegation frames"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field

SubAgentMode = Literal["single_turn", "task", "chat"]

FRAME_VERSION = 1
FRAME_TTL_HOURS = 24

MAX_TASK_CHARS = 4000
MAX_USER_PROMPT_CHARS = 4000


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
    depth: int = 0
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
