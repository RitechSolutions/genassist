from uuid import UUID

from pydantic import BaseModel


class GroupAgentItem(BaseModel):
    id: UUID
    name: str
