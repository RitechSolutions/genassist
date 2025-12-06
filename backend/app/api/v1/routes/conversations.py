import asyncio
import json
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Body, Depends, Query, WebSocket
from fastapi_injector import Injected
from starlette.websockets import WebSocketDisconnect
from app.core.exceptions.exception_handler import send_socket_error
from app.core.utils.enums.message_feedback_enum import Feedback
from app.auth.dependencies import auth, permissions, socket_auth
from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.modules.websockets.socket_room_enum import SocketRoomType
from app.schemas.agent import AgentRead
from app.schemas.conversation import ConversationRead
from app.schemas.conversation_transcript import (
    ConversationTranscriptCreate,
    InProgConvTranscrUpdate,
    InProgressConversationTranscriptFinalize,
    TranscriptSegmentFeedback,
)
from app.schemas.filter import ConversationFilter
from app.schemas.socket_principal import SocketPrincipal
from app.services.agent_config import AgentConfigService
from app.services.conversations import ConversationService
from app.services.transcript_message_service import TranscriptMessageService
from app.core.tenant_scope import get_tenant_context
from app.use_cases.chat_as_client_use_case import process_conversation_update_with_agent


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{conversation_id}",
    response_model=ConversationRead,
    dependencies=[
        Depends(auth),
        # Depends(permissions("read:conversation"))
    ],
)
async def get(
    conversation_id: UUID,
    conversation_filter: ConversationFilter = Depends(),
    service: ConversationService = Injected(ConversationService),
):
    conversation = await service.get_conversation_by_id_full(
        conversation_id, conversation_filter
    )
    return conversation


@router.post(
    "/in-progress/start",
    dependencies=[
        Depends(auth),
        Depends(permissions("create:in_progress_conversation")),
    ],
)
async def start(
    model: ConversationTranscriptCreate,
    service: ConversationService = Injected(ConversationService),
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Create a new in-progress conversation and store the partial transcript.
    """
    if model.messages:
        raise AppException(
            error_key=ErrorKey.CONVERSATION_MUST_START_EMPTY, status_code=400
        )

    if model.conversation_id:
        raise AppException(error_key=ErrorKey.ID_CANT_BE_SPECIFIED)
    userid = get_current_user_id()
    logger.debug("userid:" + str(userid))

    agent = await agent_config_service.get_by_user_id(userid)
    if not agent:
        logger.debug("agent not found")
    else:
        logger.debug("agent:" + agent.name)

    agent_read = AgentRead.model_validate(agent)
    model.operator_id = agent.operator_id
    conversation = await service.start_in_progress_conversation(model)
    logger.info("conversation:" + str(conversation))
    return {
        "message": "Conversation started",
        "conversation_id": conversation.id,
        "agent_id": agent.id,
        "agent_welcome_message": agent_read.welcome_message,
        "agent_welcome_title": agent_read.welcome_title,
        "agent_possible_queries": agent_read.possible_queries,
        "agent_thinking_phrases": agent_read.thinking_phrases,
        "agent_thinking_phrase_delay": agent_read.thinking_phrase_delay,
        "agent_has_welcome_image": agent_read.welcome_image is not None,
    }


@router.patch(
    "/in-progress/no-agent-update/{conversation_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions("update:in_progress_conversation")),
    ],
)
async def update_no_agent(
    conversation_id: UUID,
    model: InProgConvTranscrUpdate,
    service: ConversationService = Injected(ConversationService),
    socket_connection_manager: SocketConnectionManager = Injected(
        SocketConnectionManager
    ),
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Append segments to an existing in-progress conversation or create it if it doesn't exist.
    """

    # create if not exists
    conversation = await service.get_conversation_by_id(
        conversation_id, raise_not_found=False
    )
    if not conversation:
        userid = get_current_user_id()

        agent = await agent_config_service.get_by_user_id(userid)

        new_conversation_model = ConversationTranscriptCreate(
            conversation_id=conversation_id,
            messages=[],
            operator_id=agent.operator_id,
        )
        conversation = await service.start_in_progress_conversation(
            new_conversation_model
        )

    if conversation.status == ConversationStatus.FINALIZED.value:
        raise AppException(ErrorKey.CONVERSATION_FINALIZED)

    transcript_json = [segment.model_dump() for segment in model.messages]

    tenant_id = get_tenant_context()
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="message",
            payload=transcript_json[0],
            room_id=conversation_id,
            current_user_id=get_current_user_id(),
            required_topic="message",
            tenant_id=tenant_id,
        )
    )

    if conversation.status == ConversationStatus.TAKE_OVER.value:
        if any(
            message
            for message in model.messages
            if message.speaker.lower() != "customer"
        ):
            if get_current_user_id() != conversation.supervisor_id:
                raise AppException(ErrorKey.CONVERSATION_TAKEN_OVER_OTHER)

    updated_conversation = await service.update_in_progress_conversation(
        conversation_id, model
    )

    # Notify dashboard a conversation is updated
    tenant_id = get_tenant_context()
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="update",
            payload={
                "conversation_id": updated_conversation.id,
                "in_progress_hostility_score": updated_conversation.in_progress_hostility_score,
                "transcript": updated_conversation.messages[-1].text,
                "duration": updated_conversation.duration,
                "negative_reason": updated_conversation.negative_reason,
                "topic": updated_conversation.topic,
            },
            room_id=SocketRoomType.DASHBOARD,
            current_user_id=get_current_user_id(),
            required_topic="hostile",
            tenant_id=tenant_id,
        )
    )

    upd_conv_pyd: ConversationRead = ConversationRead.model_validate(
        updated_conversation
    )

    # broadcast statistics
    tenant_id = get_tenant_context()
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="statistics",
            payload=upd_conv_pyd.model_dump(),
            room_id=conversation_id,
            current_user_id=get_current_user_id(),
            required_topic="statistics",
            tenant_id=tenant_id,
        )
    )

    return updated_conversation


@router.patch(
    "/in-progress/update/{conversation_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions("update:in_progress_conversation")),
    ],
)
async def update(
    conversation_id: UUID,
    model: InProgConvTranscrUpdate,
):
    """
    Append segments to an existing in-progress conversation.
    """
    tenant_id = get_tenant_context()

    return await process_conversation_update_with_agent(
        conversation_id=conversation_id,
        model=model,
        tenant_id=tenant_id,
        current_user_id=get_current_user_id(),
    )


@router.patch(
    "/in-progress/finalize/{conversation_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions("update:in_progress_conversation")),
    ],
)
async def finalize(
    conversation_id: UUID,
    finalize: InProgressConversationTranscriptFinalize,
    service: ConversationService = Injected(ConversationService),
    socket_connection_manager: SocketConnectionManager = Injected(
        SocketConnectionManager
    ),
):
    """
    Finalize the conversation so that no more partial updates are allowed.
    Optionally trigger the final analysis or let another endpoint handle it.
    """
    tenant_id = get_tenant_context()
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="finalize",
            room_id=conversation_id,
            current_user_id=get_current_user_id(),
            required_topic="finalize",
            tenant_id=tenant_id,
        )
    )

    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="finalize",
            room_id=SocketRoomType.DASHBOARD,
            current_user_id=get_current_user_id(),
            required_topic="finalize",
            tenant_id=tenant_id,
        )
    )

    finalized_conversation_analysis = await service.finalize_in_progress_conversation(
        finalize.llm_analyst_id, conversation_id
    )
    return finalized_conversation_analysis


@router.patch(
    "/in-progress/takeover-super/{conversation_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions("takeover_in_progress_conversation")),
    ],
)
async def takeover_supervisor(
    conversation_id: UUID,
    service: ConversationService = Injected(ConversationService),
    socket_connection_manager: SocketConnectionManager = Injected(
        SocketConnectionManager
    ),
):
    """
    Take over conversation from agent by a supervisor.
    """
    conversation_taken_over = await service.supervisor_takeover_conversation(
        conversation_id
    )

    tenant_id = get_tenant_context()
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="takeover",
            room_id=conversation_taken_over.id,
            current_user_id=get_current_user_id(),
            required_topic="takeover",
            tenant_id=tenant_id,
        )
    )

    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="takeover",
            room_id=SocketRoomType.DASHBOARD,
            current_user_id=get_current_user_id(),
            required_topic="takeover",
            tenant_id=tenant_id,
        )
    )

    return conversation_taken_over


@router.get(
    "/",
    response_model=list[ConversationRead],
    dependencies=[Depends(auth), Depends(permissions("read:conversation"))],
)
async def get(
    conversation_filter: ConversationFilter = Depends(),
    conversations_service: ConversationService = Injected(ConversationService),
):
    conversations = await conversations_service.get_conversations(conversation_filter)
    return conversations


@router.get(
    "/filter/count",
    dependencies=[Depends(auth), Depends(permissions("read:conversation"))],
)
async def get(
    conversation_filter: ConversationFilter = Depends(),
    conversations_service: ConversationService = Injected(ConversationService),
):
    return await conversations_service.count_conversations(conversation_filter)


@router.patch(
    "/message/add-feedback/{message_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions("update:in_progress_conversation")),
    ],
)
async def add_message_feedback(
    message_id: UUID,
    transcript_feedback: TranscriptSegmentFeedback,
    transcript_message_service: TranscriptMessageService = Injected(
        TranscriptMessageService
    ),
):
    await transcript_message_service.add_transcript_message_feedback(
        message_id, transcript_feedback
    )
    return {
        "message": f"Successfully added message feedback, "
        f"for message id:{message_id} "
    }


@router.patch(
    "/feedback/{conversation_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions("update:in_progress_conversation")),
    ],
)
async def add_conversation_feedback(
    conversation_id: UUID,
    feedback: Feedback = Body(..., embed=True),
    feedback_message: str = Body(..., embed=True),
    conversations_service: ConversationService = Injected(ConversationService),
):
    await conversations_service.add_conversation_feedback(
        conversation_id, feedback, feedback_message
    )
    return {
        "message": f"Successfully added feedback, in conversation id:{conversation_id}"
    }


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: UUID,
    principal: SocketPrincipal = socket_auth(["read:in_progress_conversation"]),
    lang: Optional[str] = Query(default="en"),
    topics: list[str] = Query(default=["message"]),
    socket_connection_manager: SocketConnectionManager = Injected(
        SocketConnectionManager
    ),
):
    tenant_id = principal.tenant_id
    await socket_connection_manager.connect(
        websocket=websocket,
        room_id=conversation_id,
        user_id=principal.user_id,
        permissions=principal.permissions,
        tenant_id=tenant_id,
        topics=topics,
    )

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("Received data: %s", data)
    except WebSocketDisconnect:
        logger.debug(
            f"WebSocket disconnected for conversation {conversation_id} (tenant: {tenant_id})"
        )
        await socket_connection_manager.disconnect(
            websocket, conversation_id, tenant_id
        )
    except Exception as e:
        logger.exception("Unexpected WebSocket error: %s", e)
        # Attempt to disconnect even if we don't know the exact room/tenant
        try:
            await socket_connection_manager.disconnect(
                websocket, conversation_id, tenant_id
            )
        except Exception:
            # Fallback: disconnect without room info (searches all rooms)
            await socket_connection_manager.disconnect(websocket, None, None)
        await send_socket_error(websocket, ErrorKey.INTERNAL_ERROR, lang)
        await websocket.close(code=1011)


@router.websocket("/ws/dashboard/list")
async def websocket_dashboard_endpoint(
    websocket: WebSocket,
    principal: SocketPrincipal = socket_auth(["read:in_progress_conversation"]),
    lang: Optional[str] = Query(default="en"),
    topics: list[str] = Query(default=["message"]),
    socket_connection_manager: SocketConnectionManager = Injected(
        SocketConnectionManager
    ),
):
    """
    Websocket endpoint for dashboard to receive messages from the server.
    """
    tenant_id = principal.tenant_id
    await socket_connection_manager.connect(
        websocket,
        SocketRoomType.DASHBOARD,
        principal.user_id,
        principal.permissions,
        tenant_id=tenant_id,
        topics=topics,
    )

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("Received data: %s", data)
    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for dashboard (tenant: {tenant_id})")
        await socket_connection_manager.disconnect(
            websocket, SocketRoomType.DASHBOARD, tenant_id
        )
    except Exception as e:
        logger.exception("Unexpected WebSocket error: %s", e)
        # Attempt to disconnect even if we don't know the exact room/tenant
        try:
            await socket_connection_manager.disconnect(
                websocket, SocketRoomType.DASHBOARD, tenant_id
            )
        except Exception:
            # Fallback: disconnect without room info (searches all rooms)
            await socket_connection_manager.disconnect(websocket, None, None)
        await send_socket_error(websocket, ErrorKey.INTERNAL_ERROR, lang)
        await websocket.close(code=1011)
