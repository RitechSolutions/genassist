
from typing import Optional
from pydantic import BaseModel


class ZendeskRequester(BaseModel):
    name: Optional[str]
    email: Optional[str]


class ZendeskClosedPayload(BaseModel):
    ticket_id: int
    subject: Optional[str] = None
    updated_at: Optional[str] = None
    requester: Optional[ZendeskRequester] = None
    status: Optional[str] = None
    custom_fields: Optional[list[dict]] = None
    tags: Optional[list[str]]  = None

