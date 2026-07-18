"""Persisted shapes for sub-agent delegation frames.

A task/chat delegation pauses the parent and stores a frame on the root
thread's conversation metadata; the next user turn reads it back, routes to the
child, and on completion re-enters the parent with ``ParentResume``. All models
forbid extra keys so a corrupt/old payload fails validation loudly rather than
silently carrying junk into a live run.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FRAME_VERSION = 1
FRAME_TTL_HOURS = 24

# Field caps — oversize fails the handoff (see session.write_frame) rather than
# truncating, so nothing a downstream template depends on is silently dropped.
MAX_TASK_CHARS = 4000
MAX_USER_PROMPT_CHARS = 4000
MAX_DIALOGUE_TURNS = 10
MAX_DIALOGUE_TURN_CHARS = 2000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expiry_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=FRAME_TTL_HOURS)).isoformat()


class ParentResume(BaseModel):
    """Snapshot the parent agent needs to continue after a child hands back.

    A resume starts a fresh WorkflowState at the parent node, so node_outputs,
    node_execution_status and accumulated steps/tools would be lost without this.
    """

    model_config = ConfigDict(extra="forbid")

    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    node_execution_status: Dict[str, Any] = Field(default_factory=dict)
    request_context: Dict[str, Any] = Field(default_factory=dict)
    user_prompt: str = Field(default="", max_length=MAX_USER_PROMPT_CHARS)
    delegation_dialogue: List[str] = Field(default_factory=list)
    completed_count: int = 0
    accumulated_steps: List[Any] = Field(default_factory=list)
    accumulated_tools_used: List[Any] = Field(default_factory=list)

    @field_validator("delegation_dialogue")
    @classmethod
    def _cap_dialogue(cls, value: List[str]) -> List[str]:
        if len(value) > MAX_DIALOGUE_TURNS:
            raise ValueError(f"delegation_dialogue exceeds {MAX_DIALOGUE_TURNS} turns")
        for turn in value:
            if len(turn) > MAX_DIALOGUE_TURN_CHARS:
                raise ValueError(f"dialogue turn exceeds {MAX_DIALOGUE_TURN_CHARS} chars")
        return value


class SubAgentFrame(BaseModel):
    """One paused parent→child delegation on the stack.

    Identity fields (parent_node_id, workflow_id, invocation_id) gate ownership
    and branch isolation; ``parent_resume`` is the cargo replayed on hand-back.
    """

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
    """The ordered frame stack for one agent on one root thread (top = last)."""

    model_config = ConfigDict(extra="forbid")

    version: int = FRAME_VERSION
    agent_id: str
    frames: List[SubAgentFrame] = Field(default_factory=list)

    def top(self) -> SubAgentFrame | None:
        return self.frames[-1] if self.frames else None
