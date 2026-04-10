from dataclasses import dataclass, field
from fastapi import WebSocket


@dataclass(slots=True)
class Connection:
    websocket: WebSocket
    user_id: str
    permissions: list[str]
    tenant_id: str
    topics: set[str] = field(default_factory=set)
    connected_at: float = 0.0
    last_pong: float = 0.0
