import asyncio
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Body, Depends, Query, Request, WebSocket
from fastapi_injector import Injected
from starlette.websockets import WebSocketDisconnect
from app.core.exceptions.exception_handler import send_socket_error
from app.core.utils.enums.message_feedback_enum import Feedback
from app.auth.dependencies import (
    auth,
    permissions,
    socket_auth,
    auth_for_conversation_update,
)
from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.middlewares.rate_limit_middleware import (
    limiter,
    get_conversation_identifier,
    get_agent_rate_limit_start,
    get_agent_rate_limit_start_hour,
    get_agent_rate_limit_update,
    get_agent_rate_limit_update_hour,
)
from app.auth.dependencies_agent_security import (
    get_agent_for_start,
    get_agent_for_update,
)
from app.core.agent_security_utils import apply_agent_cors_headers
from fastapi import Response
from fastapi.responses import JSONResponse
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
from app.services.auth import AuthService
from app.core.tenant_scope import get_tenant_context
from app.use_cases.chat_as_client_use_case import process_conversation_update_with_agent
from app.core.permissions.constants import Permissions as P
from app.core.utils.recaptcha_utils import verify_recaptcha_token


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/{conversation_id}",
    response_model=ConversationRead,
    dependencies=[
        Depends(auth),
        # Depends(permissions(P.Conversation.READ))
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
        Depends(permissions(P.Conversation.CREATE_IN_PROGRESS)),
        Depends(get_agent_for_start),  # Get agent early for rate limiting and CORS
    ],
)
@limiter.limit(get_agent_rate_limit_start)
@limiter.limit(get_agent_rate_limit_start_hour)
async def start(
    request: Request,
    model: ConversationTranscriptCreate,
    response: Response,
    service: ConversationService = Injected(ConversationService),
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
    auth_service: AuthService = Injected(AuthService),
):
    """
    Create a new in-progress conversation and store the partial transcript.
    If agent.security_settings.token_based_auth is true, returns a JWT token for secure frontend access.
    """
    # Get agent from request.state (set by get_agent_for_start dependency)
    agent = getattr(request.state, "agent", None)
    if not agent:
        logger.debug("agent not found")
        raise AppException(error_key=ErrorKey.AGENT_NOT_FOUND, status_code=404)

    logger.debug(f"agent: {agent.name}")

    # Verify reCAPTCHA token if it is present, using agent-specific settings
    is_valid, score, reason = verify_recaptcha_token(model.recaptcha_token, agent=agent)
    if not is_valid:
        logger.warning(f"reCAPTCHA verification failed: {reason}")
        raise AppException(
            error_key=ErrorKey.RECAPTCHA_VERIFICATION_FAILED, status_code=403
        )

    if model.messages:
        raise AppException(
            error_key=ErrorKey.CONVERSATION_MUST_START_EMPTY, status_code=400
        )

    if model.conversation_id:
        raise AppException(error_key=ErrorKey.ID_CANT_BE_SPECIFIED)

    agent_read = AgentRead.model_validate(agent)
    model.operator_id = agent.operator_id
    conversation = await service.start_in_progress_conversation(model)
    logger.info("conversation:" + str(conversation))

    # Use model_dump with json mode to ensure all values are JSON-serializable (UUIDs converted to strings)
    agent_data = agent_read.model_dump(mode="json")

    response = {
        "message": "Conversation started",
        "conversation_id": str(conversation.id),
        "agent_id": str(agent.id),
        "agent_welcome_message": agent_data.get("welcome_message"),
        "agent_welcome_title": agent_data.get("welcome_title"),
        "agent_possible_queries": agent_data.get("possible_queries"),
        "agent_thinking_phrases": agent_data.get("thinking_phrases"),
        "agent_thinking_phrase_delay": agent_data.get("thinking_phrase_delay"),
        "agent_has_welcome_image": agent_data.get("welcome_image") is not None,
    }

    # If agent requires authentication, generate and return a guest JWT token
    token_based_auth = (
        agent_read.security_settings.token_based_auth
        if agent_read.security_settings
        and agent_read.security_settings.token_based_auth
        else False
    )
    if token_based_auth:
        tenant_id = get_tenant_context()
        # Use agent-specific token expiration if set, otherwise use default (24 hours)
        from datetime import timedelta

        expires_delta = None
        if agent.security_settings and agent.security_settings.token_expiration_minutes:
            expires_delta = timedelta(
                minutes=agent.security_settings.token_expiration_minutes
            )
        # Include user_id from the API key used to start the conversation
        userid = get_current_user_id()
        guest_token = auth_service.create_guest_token(
            tenant_id=tenant_id,
            agent_id=str(agent.id),
            conversation_id=str(conversation.id),
            user_id=str(userid) if userid else None,
            expires_delta=expires_delta,
        )
        response["guest_token"] = guest_token

    # Apply agent-specific CORS headers
    agent_security_settings = (
        agent.security_settings
        if agent and hasattr(agent, "security_settings")
        else None
    )

    json_response = JSONResponse(content=response)
    apply_agent_cors_headers(request, json_response, agent_security_settings)

    return json_response


@router.patch(
    "/in-progress/no-agent-update/{conversation_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Conversation.UPDATE_IN_PROGRESS)),
        Depends(get_agent_for_update),  # Get agent early for rate limiting and CORS
    ],
)
@limiter.limit(get_agent_rate_limit_update, key_func=get_conversation_identifier)
@limiter.limit(get_agent_rate_limit_update_hour, key_func=get_conversation_identifier)
async def update_no_agent(
    request: Request,
    conversation_id: UUID,
    model: InProgConvTranscrUpdate,
    response: Response,
    service: ConversationService = Injected(ConversationService),
    socket_connection_manager: SocketConnectionManager = Injected(
        SocketConnectionManager
    ),
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Append segments to an existing in-progress conversation or create it if it doesn't exist.
    """

    # Get agent from request.state (set by get_agent_for_update dependency)
    agent = getattr(request.state, "agent", None)

    # create if not exists
    conversation = await service.get_conversation_by_id(
        conversation_id, raise_not_found=False
    )
    if not conversation:
        if not agent:
            userid = get_current_user_id()
            agent = await agent_config_service.get_by_user_id(userid)
            request.state.agent = agent

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

    # Apply agent-specific CORS headers
    agent_security_settings = (
        agent.security_settings
        if agent and hasattr(agent, "security_settings")
        else None
    )

    json_response = JSONResponse(content=upd_conv_pyd.model_dump())
    apply_agent_cors_headers(request, json_response, agent_security_settings)

    return json_response


@router.patch(
    "/in-progress/update/{conversation_id}",
    dependencies=[
        Depends(auth_for_conversation_update),
        Depends(permissions(P.Conversation.UPDATE_IN_PROGRESS)),
        Depends(get_agent_for_update),
    ],
)
@limiter.limit(get_agent_rate_limit_update, key_func=get_conversation_identifier)
@limiter.limit(get_agent_rate_limit_update_hour, key_func=get_conversation_identifier)
async def update(
    request: Request,
    conversation_id: UUID,
    model: InProgConvTranscrUpdate,
):
    """
    Append segments to an existing in-progress conversation.
    If agent.security_settings.token_based_auth is true, only accepts JWT tokens (rejects API keys).
    """
    tenant_id = get_tenant_context()

    updated_conversation = await process_conversation_update_with_agent(
        conversation_id=conversation_id,
        model=model,
        tenant_id=tenant_id,
        current_user_id=get_current_user_id(),
    )

    upd_conv_pyd: ConversationRead = ConversationRead.model_validate(
        updated_conversation
    )

    agent = getattr(request.state, "agent", None)
    agent_security_settings = (
        agent.security_settings
        if agent and hasattr(agent, "security_settings")
        else None
    )

    json_response = JSONResponse(content=upd_conv_pyd.model_dump(mode="json"))
    apply_agent_cors_headers(request, json_response, agent_security_settings)

    return json_response


@router.patch(
    "/in-progress/finalize/{conversation_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Conversation.UPDATE_IN_PROGRESS)),
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
        Depends(permissions(P.Conversation.TAKEOVER_IN_PROGRESS)),
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
    dependencies=[Depends(auth), Depends(permissions(P.Conversation.READ))],
)
async def get(
    conversation_filter: ConversationFilter = Depends(),
    conversations_service: ConversationService = Injected(ConversationService),
):
    conversations = await conversations_service.get_conversations(conversation_filter)
    return conversations


@router.get(
    "/filter/count",
    dependencies=[Depends(auth), Depends(permissions(P.Conversation.READ))],
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
        Depends(permissions(P.Conversation.UPDATE_IN_PROGRESS)),
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
        Depends(permissions(P.Conversation.UPDATE_IN_PROGRESS)),
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
