from pydantic import BaseModel


class NotificationPreferencesRead(BaseModel):
    conversation_started: bool
    conversation_hostility: bool
    conversation_finalized_hostility: bool
    workflow_failed: bool
    can_manage_workflow_failed: bool


class NotificationPreferencesUpdate(BaseModel):
    conversation_started: bool | None = None
    conversation_hostility: bool | None = None
    conversation_finalized_hostility: bool | None = None
    workflow_failed: bool | None = None
