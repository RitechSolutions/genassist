from datetime import datetime
from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: str
    title: str
    description: str
    timestamp: datetime
    type: str
    action_url: str


class NotificationFeedResponse(BaseModel):
    items: list[NotificationItem]
    has_more: bool = False
