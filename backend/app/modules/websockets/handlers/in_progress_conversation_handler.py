from typing import Optional
<<<<<<< HEAD

=======
>>>>>>> development
from fastapi import WebSocket
from jose import JWTError, ExpiredSignatureError
from uuid import UUID
import logging
from starlette.websockets import WebSocketDisconnect
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_handler import send_socket_error
from app.auth.utils import has_permission, socket_user_id

logger = logging.getLogger(__name__)

<<<<<<< HEAD
async def handle_conversation_socket(
    websocket: WebSocket,
    conversation_id: UUID,
    access_token: Optional[str],
    api_key: Optional[str],
    lang: str,
    auth_service,
    socket_connection_manager: SocketConnectionManager
):
=======

async def handle_conversation_socket(
        websocket: WebSocket,
        conversation_id: UUID,
        access_token: Optional[str],
        api_key: Optional[str],
        lang: str,
        auth_service,
        socket_connection_manager: SocketConnectionManager,
        topics: list[str],
        ):
>>>>>>> development
    try:
        user = None
        api_key_object = None

        if access_token:
            user = await auth_service.decode_jwt(access_token)
            socket_user_id.set(user.id)
        elif api_key:
            api_key_object = await auth_service.authenticate_api_key(api_key)
            socket_user_id.set(api_key_object.user.id)

        principal = user if user is not None else api_key_object
        user_id = user.id if user is not None else api_key_object.user.id
        permissions = user.permissions if user is not None else api_key_object.permissions

        if principal is None or not has_permission(permissions, "read:in_progress_conversation"):
            await websocket.close(code=4403, reason="Invalid permissions")
            return

    except ExpiredSignatureError:
        await websocket.close(code=4401, reason="Token expired")
        return
    except JWTError:
        await websocket.close(code=4401, reason="Invalid token")
        return
    except Exception as e:
        logger.exception("Unexpected WebSocket auth error: %s", e)
        await websocket.close(code=1011, reason="Authentication failure")
        return

<<<<<<< HEAD
    await socket_connection_manager.connect(websocket, conversation_id, user_id, permissions)
=======
    await socket_connection_manager.connect(websocket, conversation_id, user_id, permissions, topics)
>>>>>>> development

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("Received data: %s", data)
    except WebSocketDisconnect:
        socket_connection_manager.disconnect(websocket, conversation_id)
    except Exception as e:
        logger.exception("Unexpected WebSocket error: %s", e)
        await send_socket_error(websocket, ErrorKey.INTERNAL_ERROR, lang)
        await websocket.close(code=1011)
