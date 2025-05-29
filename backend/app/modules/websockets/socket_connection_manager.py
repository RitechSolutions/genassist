import json
import logging
<<<<<<< HEAD
import json
=======
from typing import Dict, List, Tuple
from uuid import UUID

from fastapi.websockets import WebSocket
>>>>>>> development


logger = logging.getLogger(__name__)

class SocketConnectionManager:
    def __init__(self):
        self.active_connections: Dict[UUID, List[Tuple[WebSocket, UUID, List[str], list[str]]]] = {}

<<<<<<< HEAD
    async def connect(self, websocket: WebSocket, conversation_id: UUID, user_id: UUID, permissions: list[str]):
        await websocket.accept()
        self.active_connections.setdefault(conversation_id, []).append((websocket, user_id, permissions))
=======
    async def connect(self, websocket: WebSocket, conversation_id: UUID, user_id: UUID, permissions: list[str], topics: list[str]):
        await websocket.accept()
        self.active_connections.setdefault(conversation_id, []).append((websocket, user_id, permissions, topics))
>>>>>>> development

    def disconnect(self, websocket: WebSocket, conversation_id: UUID):
        self.active_connections[conversation_id] = [
            (ws, uid, p, t) for (ws, uid, p, t) in self.active_connections.get(conversation_id, [])
            if ws != websocket
        ]
        if not self.active_connections[conversation_id]:
            del self.active_connections[conversation_id]

<<<<<<< HEAD
    async def broadcast(self, message_type: str, conversation_id: UUID, current_user_id: UUID, transcript: list[dict] = None):
        message = {
            "type": message_type,
            "transcript": transcript,
            }
        for websocket, user_id, _ in self.active_connections.get(conversation_id, []):
            try:
                if current_user_id != user_id:
=======
    async def broadcast(self, msg_type: str, conversation_id: UUID, current_user_id: UUID, payload =
    None, required_topic = "messages"):
        message = {
            "type": msg_type,
            "payload": payload,
            }
        for websocket, user_id, _, topics in self.active_connections.get(conversation_id, []):
            try:
                if (
                        # current_user_id != user_id and
                        required_topic in topics):
>>>>>>> development
                    await websocket.send_text(json.dumps(message, default=str))
            except Exception as e:
                self.disconnect(websocket, conversation_id)
                logger.warning(f"Failed to send message to a client: {e}")
