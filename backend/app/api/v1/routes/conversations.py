import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Request, WebSocket
from fastapi.responses import JSONResponse
from fastapi_injector import Injected
from starlette.websockets import WebSocketDisconnect

from app.auth.dependencies import (
    auth,
    auth_for_conversation_update,
    permissions,
    socket_auth,
)
from app.auth.dependencies_agent_security import (
    get_agent_for_start,
    get_agent_for_update,
)
from app.auth.utils import get_current_user_id
from app.cache.redis_cache import invalidate_cache
from app.core.agent_security_utils import apply_agent_cors_headers
from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import send_socket_error
from app.core.permissions.constants import Permissions as P
from app.core.tenant_scope import get_tenant_context
from app.core.utils.bi_utils import increment_feedback
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.core.utils.enums.message_feedback_enum import Feedback
from app.core.utils.recaptcha_utils import verify_recaptcha_token
from app.middlewares.rate_limit_middleware import (
    get_agent_rate_limit_start,
    get_agent_rate_limit_start_hour,
    get_agent_rate_limit_update,
    get_agent_rate_limit_update_hour,
    get_conversation_identifier,
    limiter,
)
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.modules.websockets.socket_room_enum import SocketRoomType
from app.schemas.agent import AgentRead
from app.schemas.conversation import (
    ConversationPaginatedResponse,
    ConversationRead,
    InProgressPollResponse,
)
from app.schemas.conversation_transcript import (
    ConversationStartWithRecaptchaToken,
    ConversationTranscriptCreate,
    ConversationUpdateWithRecaptchaToken,
    InProgConvTranscrUpdate,
    InProgressConversationTranscriptFinalize,
    TranscriptSegmentFeedback,
)
from app.schemas.filter import ConversationFilter
from app.schemas.socket_principal import SocketPrincipal
from app.services.agent_config import AgentConfigService
from app.services.agent_response_log import AgentResponseLogService
from app.services.analytics_realtime import (
    update_conversation_finalized,
    update_conversation_started,
    update_feedback_given,
)
from app.services.auth import AuthService
from app.services.conversations import ConversationService
from app.services.dashboard import DashboardService
from app.services.file_manager import FileManagerService
from app.services.transcript_message_service import TranscriptMessageService
from app.services.translations import TranslationsService
from app.use_cases.chat_as_client_use_case import (
    process_attachments_from_metadata,
    process_conversation_update_with_agent,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/in-progress/agent-info",
    dependencies=[
        Depends(auth),
        Depends(get_agent_for_start),  # Get agent early for CORS and auth
        Depends(permissions(P.Conversation.CREATE_IN_PROGRESS)),
    ],
)
async def get_agent_info(
    request: Request,
    translations_service: TranslationsService = Injected(TranslationsService),
):
    """
    Return agent metadata needed before a conversation starts (e.g. supported languages).
    """
    agent = getattr(request.state, "agent", None)
    if not agent:
        logger.debug("agent not found")
        raise AppException(error_key=ErrorKey.AGENT_NOT_FOUND, status_code=404)

    available_languages = await translations_service.get_languages_for_prefix(f"agent.{agent.id}.")

    response = {
        "agent_id": str(agent.id),
        "agent_available_languages": available_languages,
    }

    agent_security_settings = agent.security_settings if hasattr(agent, "security_settings") else None
    json_response = JSONResponse(content=response)
    apply_agent_cors_headers(request, json_response, agent_security_settings)
    return json_response


@router.get(
    "/in-progress/agent-chat-locales",
    dependencies=[
        Depends(auth),
        Depends(get_agent_for_start),
        Depends(permissions(P.Conversation.CREATE_IN_PROGRESS)),
    ],
)
async def get_agent_chat_locales(
    request: Request,
    translations_service: TranslationsService = Injected(TranslationsService),
):
    """
    Return welcome / quick queries / thinking strings for every locale that has agent translations,
    plus the tenant default language. Lets the widget switch UI language without restarting the conversation.
    """
    agent = getattr(request.state, "agent", None)
    if not agent:
        logger.debug("agent not found")
        raise AppException(error_key=ErrorKey.AGENT_NOT_FOUND, status_code=404)

    agent_read = AgentRead.model_validate(agent)
    agent_data = agent_read.model_dump(mode="json")

    agent_prefix = f"agent.{agent.id}"
    possible_queries = agent_data.get("possible_queries") or []
    thinking_phrases = agent_data.get("thinking_phrases") or []

    translation_items: dict[str, str | None] = {
        f"{agent_prefix}.welcome_message": agent_data.get("welcome_message"),
        f"{agent_prefix}.welcome_title": agent_data.get("welcome_title"),
        f"{agent_prefix}.input_disclaimer_html": agent_data.get("input_disclaimer_html"),
    }
    for idx, query in enumerate(possible_queries):
        translation_items[f"{agent_prefix}.possible_queries.{idx}"] = query
    for idx, phrase in enumerate(thinking_phrases):
        translation_items[f"{agent_prefix}.thinking_phrases.{idx}"] = phrase

    available_languages = await translations_service.get_languages_for_prefix(f"agent.{agent.id}.")
    default_lang = (settings.DEFAULT_LANGUAGE or "en").split("-")[0].lower()
    lang_codes = sorted(set(available_languages) | {default_lang})

    locales: dict[str, dict[str, object]] = {}
    for code in lang_codes:
        resolved = await translations_service.resolve_many_for_lang(translation_items, code)
        welcome_message = resolved.get(f"{agent_prefix}.welcome_message")
        welcome_title = resolved.get(f"{agent_prefix}.welcome_title")
        input_disclaimer_html = resolved.get(f"{agent_prefix}.input_disclaimer_html")
        resolved_queries = [
            resolved.get(f"{agent_prefix}.possible_queries.{idx}") or query for idx, query in enumerate(possible_queries)
        ]
        resolved_phrases = [
            resolved.get(f"{agent_prefix}.thinking_phrases.{idx}") or phrase for idx, phrase in enumerate(thinking_phrases)
        ]
        locales[code] = {
            "welcome_message": welcome_message,
            "welcome_title": welcome_title,
            "input_disclaimer_html": input_disclaimer_html,
            "possible_queries": resolved_queries,
            "thinking_phrases": resolved_phrases,
        }

    response = {
        "agent_id": str(agent.id),
        "agent_available_languages": available_languages,
        "agent_thinking_phrase_delay": agent_data.get("thinking_phrase_delay"),
        "agent_chat_input_metadata": agent_data.get("workflow"),
        "agent_has_welcome_image": agent_data.get("welcome_image") is not None,
        "locales": locales,
    }

    agent_security_settings = agent.security_settings if hasattr(agent, "security_settings") else None
    json_response = JSONResponse(content=response)
    apply_agent_cors_headers(request, json_response, agent_security_settings)
    return json_response


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
    conversation = await service.get_conversation_by_id_full(conversation_id, conversation_filter)
    return conversation


@router.post(
    "/in-progress/start",
    dependencies=[
        Depends(auth),
        Depends(get_agent_for_start),  # Get agent early for rate limiting and CORS
        Depends(permissions(P.Conversation.CREATE_IN_PROGRESS)),
    ],
)
@limiter.limit(get_agent_rate_limit_start)
@limiter.limit(get_agent_rate_limit_start_hour)
async def start(
    request: Request,
    model: ConversationStartWithRecaptchaToken,
    service: ConversationService = Injected(ConversationService),
    auth_service: AuthService = Injected(AuthService),
    translations_service: TranslationsService = Injected(TranslationsService),
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

    # Verify reCAPTCHA token if it is present in the request body, using agent-specific settings
    reCaptchaToken = model.recaptcha_token or None
    is_valid, score, reason = verify_recaptcha_token(reCaptchaToken, agent=agent)
    if not is_valid:
        logger.warning(f"reCAPTCHA verification failed: {reason}")
        raise AppException(error_key=ErrorKey.RECAPTCHA_VERIFICATION_FAILED, status_code=403)

    if model.messages:
        raise AppException(error_key=ErrorKey.CONVERSATION_MUST_START_EMPTY, status_code=400)

    if model.conversation_id:
        raise AppException(error_key=ErrorKey.ID_CANT_BE_SPECIFIED)

    agent_read = AgentRead.model_validate(agent)
    model.operator_id = agent.operator_id
    conversation = await service.start_in_progress_conversation(model)

    # Increment conversation counters in background
    _ = asyncio.create_task(update_conversation_started(agent.id))

    # Notify dashboard that a new conversation was started (e.g. from chatbot)
    tenant_id = get_tenant_context()

    # Use model_dump with json mode to ensure all values are JSON-serializable (UUIDs converted to strings)
    agent_data = agent_read.model_dump(mode="json")

    accept_lang = request.headers.get("accept-language")

    # Build a batch of all translation keys to resolve in a single pass
    agent_prefix = f"agent.{agent.id}"
    possible_queries = agent_data.get("possible_queries") or []
    thinking_phrases = agent_data.get("thinking_phrases") or []

    translation_items: dict[str, str | None] = {
        f"{agent_prefix}.welcome_message": agent_data.get("welcome_message"),
        f"{agent_prefix}.welcome_title": agent_data.get("welcome_title"),
        f"{agent_prefix}.input_disclaimer_html": agent_data.get("input_disclaimer_html"),
    }
    for idx, query in enumerate(possible_queries):
        translation_items[f"{agent_prefix}.possible_queries.{idx}"] = query
    for idx, phrase in enumerate(thinking_phrases):
        translation_items[f"{agent_prefix}.thinking_phrases.{idx}"] = phrase

    resolved = await translations_service.resolve_many(translation_items, accept_lang)

    welcome_message = resolved.get(f"{agent_prefix}.welcome_message")
    welcome_title = resolved.get(f"{agent_prefix}.welcome_title")
    input_disclaimer_html = resolved.get(f"{agent_prefix}.input_disclaimer_html")
    resolved_queries = [
        resolved.get(f"{agent_prefix}.possible_queries.{idx}") or query for idx, query in enumerate(possible_queries)
    ]
    resolved_phrases = [
        resolved.get(f"{agent_prefix}.thinking_phrases.{idx}") or phrase for idx, phrase in enumerate(thinking_phrases)
    ]
    available_languages = await translations_service.get_languages_for_prefix(f"agent.{agent.id}.")

    response = {
        "message": "Conversation started",
        "conversation_id": str(conversation.id),
        "agent_id": str(agent.id),
        "agent_welcome_message": welcome_message,
        "agent_welcome_title": welcome_title,
        "agent_possible_queries": resolved_queries,
        "agent_thinking_phrases": resolved_phrases,
        "agent_thinking_phrase_delay": agent_data.get("thinking_phrase_delay"),
        "agent_has_welcome_image": agent_data.get("welcome_image") is not None,
        "agent_chat_input_metadata": agent_data.get("workflow"),
        "agent_input_disclaimer_html": input_disclaimer_html,
        "agent_available_languages": available_languages,
    }

    # If agent requires authentication, generate and return a guest JWT token
    token_based_auth = (
        agent_read.security_settings.token_based_auth
        if agent_read.security_settings and agent_read.security_settings.token_based_auth
        else False
    )
    if token_based_auth:
        tenant_id = get_tenant_context()
        # Use agent-specific token expiration if set, otherwise use default (24 hours)
        from datetime import timedelta

        expires_delta = None
        if agent.security_settings and agent.security_settings.token_expiration_minutes:
            expires_delta = timedelta(minutes=agent.security_settings.token_expiration_minutes)
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
    agent_security_settings = agent.security_settings if hasattr(agent, "security_settings") else None

    json_response = JSONResponse(content=response)
    apply_agent_cors_headers(request, json_response, agent_security_settings)

    return json_response


@router.get(
    "/in-progress/poll/{conversation_id}",
    response_model=InProgressPollResponse,
    dependencies=[
        Depends(get_agent_for_update),
        Depends(auth_for_conversation_update),
        Depends(permissions(P.Conversation.UPDATE_IN_PROGRESS)),
    ],
)
@limiter.limit(get_agent_rate_limit_update, key_func=get_conversation_identifier)
@limiter.limit(get_agent_rate_limit_update_hour, key_func=get_conversation_identifier)
async def poll_in_progress(
    request: Request,
    conversation_id: UUID,
    service: ConversationService = Injected(ConversationService),
):
    """
    Heartbeat polling for in-progress conversation when WebSocket is disabled.
    Returns status and messages so the client can sync state (new messages, finalized, takeover).
    Uses a short (2s) cache to avoid DB hammering; cache is invalidated on update/finalize.
    """
    try:
        payload = await service.get_in_progress_poll_data(conversation_id)
    except AppException as e:
        if e.status_code == 404:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND, status_code=404)
        raise
    json_response = JSONResponse(content=payload.model_dump(mode="json"))
    agent = getattr(request.state, "agent", None)
    agent_security_settings = agent.security_settings if agent and hasattr(agent, "security_settings") else None
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
    service: ConversationService = Injected(ConversationService),
    socket_connection_manager: SocketConnectionManager = Injected(SocketConnectionManager),
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Append segments to an existing in-progress conversation or create it if it doesn't exist.
    """

    # Get agent from request.state (set by get_agent_for_update dependency)
    agent = getattr(request.state, "agent", None)

    # create if not exists
    conversation = await service.get_conversation_by_id(conversation_id, raise_not_found=False)
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
        conversation = await service.start_in_progress_conversation(new_conversation_model)

    if conversation.status == ConversationStatus.FINALIZED.value:
        raise AppException(ErrorKey.CONVERSATION_FINALIZED)

    transcript_json = [segment.model_dump() for segment in model.messages]

    tenant_id = get_tenant_context()
    if transcript_json:
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
        if any(message for message in model.messages if message.speaker.lower() != "customer"):
            if get_current_user_id() != conversation.supervisor_id:
                raise AppException(ErrorKey.CONVERSATION_TAKEN_OVER_OTHER)

    updated_conversation = await service.update_in_progress_conversation(conversation_id, model)

    await invalidate_cache("conversations:in_progress_poll", conversation_id)

    # Notify dashboard a conversation is updated
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
                "thumbs_up_count": updated_conversation.thumbs_up_count,
                "thumbs_down_count": updated_conversation.thumbs_down_count,
            },
            room_id=SocketRoomType.DASHBOARD,
            current_user_id=get_current_user_id(),
            required_topic="update",
            tenant_id=tenant_id,
        )
    )

    upd_conv_pyd: ConversationRead = ConversationRead.model_validate(updated_conversation)

    # broadcast statistics
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
    agent_security_settings = agent.security_settings if agent and hasattr(agent, "security_settings") else None

    json_response = JSONResponse(content=upd_conv_pyd.model_dump())
    apply_agent_cors_headers(request, json_response, agent_security_settings)

    return json_response


@router.patch(
    "/in-progress/update/{conversation_id}",
    dependencies=[
        Depends(get_agent_for_update),
        Depends(auth_for_conversation_update),
        Depends(permissions(P.Conversation.UPDATE_IN_PROGRESS)),
    ],
)
@limiter.limit(get_agent_rate_limit_update, key_func=get_conversation_identifier)
@limiter.limit(get_agent_rate_limit_update_hour, key_func=get_conversation_identifier)
async def update(
    request: Request,
    conversation_id: UUID,
    model: ConversationUpdateWithRecaptchaToken,
    file_manager_service: FileManagerService = Injected(FileManagerService),
):
    """
    Append segments to an existing in-progress conversation.
    If agent.security_settings.token_based_auth is true, only accepts JWT tokens (rejects API keys).
    """
    tenant_id = get_tenant_context()

    # Get agent from request.state (set by get_agent_for_start dependency)
    agent = getattr(request.state, "agent", None)
    if not agent:
        logger.debug("agent not found")
        raise AppException(error_key=ErrorKey.AGENT_NOT_FOUND, status_code=404)

    # validate recaptcha token
    reCaptchaToken = model.recaptcha_token or None
    is_valid, score, reason = verify_recaptcha_token(reCaptchaToken, agent=agent)
    if not is_valid:
        logger.warning(f"reCAPTCHA verification failed: {reason}")
        raise AppException(error_key=ErrorKey.RECAPTCHA_VERIFICATION_FAILED, status_code=403)

    # process attachments from metadata
    await process_attachments_from_metadata(
        base_url=str(request.base_url).rstrip("/"),
        conversation_id=conversation_id,
        model=model,
        tenant_id=tenant_id,
        current_user_id=get_current_user_id(),
        file_manager_service=file_manager_service,
    )

    updated_conversation = await process_conversation_update_with_agent(
        conversation_id=conversation_id,
        model=model,
        tenant_id=tenant_id,
        current_user_id=get_current_user_id(),
    )

    # invalidate the cache for the conversation
    await invalidate_cache("conversations:in_progress_poll", conversation_id)

    upd_conv_pyd: ConversationRead = ConversationRead.model_validate(updated_conversation)

    agent_security_settings = agent.security_settings if agent and hasattr(agent, "security_settings") else None

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
    socket_connection_manager: SocketConnectionManager = Injected(SocketConnectionManager),
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Finalize the conversation so that no more partial updates are allowed.
    Optionally trigger the final analysis or let another endpoint handle it.
    """

    def notify_socket(roomId: str):
        tenant_id = get_tenant_context()

        _ = asyncio.create_task(
            socket_connection_manager.broadcast(
                msg_type="finalize",
                room_id=roomId,
                current_user_id=get_current_user_id(),
                required_topic="finalize",
                tenant_id=tenant_id,
            )
        )

    # Notify dashboard and conversation room
    notify_socket(conversation_id)
    notify_socket(SocketRoomType.DASHBOARD)

    # Resolve analyst: explicit override > agent's configured analyst > default seed
    analyst_id = finalize.llm_analyst_id
    if not analyst_id:
        conversation = await service.get_conversation_by_id(conversation_id, raise_not_found=False)
        if conversation:
            agent = await agent_config_service.get_by_operator_id(conversation.operator_id)
            if agent and agent.llm_analyst_id:
                analyst_id = agent.llm_analyst_id

    finalized_conversation_analysis = await service.finalize_in_progress_conversation(
        conversation_id=conversation_id,
        llm_analyst_id=analyst_id,
    )

    # Increment finalized conversation counters in background
    _ = asyncio.create_task(update_conversation_finalized(conversation_id))

    await invalidate_cache("conversations:in_progress_poll", conversation_id)
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
    socket_connection_manager: SocketConnectionManager = Injected(SocketConnectionManager),
):
    """
    Take over conversation from agent by a supervisor.
    """
    conversation_taken_over = await service.supervisor_takeover_conversation(conversation_id)

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
    "",
    response_model=ConversationPaginatedResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Conversation.READ))],
)
async def get_conversations_list(
    conversation_filter: ConversationFilter = Depends(),
    conversations_service: ConversationService = Injected(ConversationService),
):
    """Get paginated list of conversations with total count."""
    conversations = await conversations_service.get_conversations(conversation_filter)
    total = await conversations_service.count_conversations(conversation_filter)

    # Calculate pagination info
    page = (conversation_filter.skip // conversation_filter.limit) + 1 if conversation_filter.limit > 0 else 1
    has_more = (conversation_filter.skip + len(conversations)) < total

    return ConversationPaginatedResponse(
        items=conversations,
        total=total,
        page=page,
        page_size=conversation_filter.limit,
        has_more=has_more,
    )


@router.get(
    "/filter/count",
    dependencies=[Depends(auth), Depends(permissions(P.Conversation.READ))],
)
async def get_conversation_count(
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
    transcript_message_service: TranscriptMessageService = Injected(TranscriptMessageService),
    conversation_service: ConversationService = Injected(ConversationService),
):
    _, conversation_id, previous_feedback = await transcript_message_service.add_transcript_message_feedback(
        message_id, transcript_feedback
    )

    # Get the conversation and update thumbs up/down counts
    conversation = await conversation_service.get_conversation_by_id(conversation_id, raise_not_found=True)

    # Update conversation thumbs up/down counts based on feedback type
    increment_feedback(conversation, transcript_feedback, previous_feedback)

    # Persist the updated conversation
    await conversation_service.update_conversation(conversation)

    # Fire incremental analytics update for thumbs in background
    is_thumbs_up = transcript_feedback.feedback in (Feedback.GOOD, Feedback.VERY_GOOD)
    _ = asyncio.create_task(update_feedback_given(conversation_id, is_thumbs_up))

    return {"message": f"Successfully added message feedback, for message id:{message_id} "}


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
    await conversations_service.add_conversation_feedback(conversation_id, feedback, feedback_message)
    return {"message": f"Successfully added feedback, in conversation id:{conversation_id}"}


@router.get(
    "/{conversation_id}/agent-response-logs",
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Conversation.READ)),
    ],
)
async def get_agent_response_logs_by_conversation(
    conversation_id: UUID,
    agent_response_log_service: AgentResponseLogService = Injected(AgentResponseLogService),
):
    """
    Return token usage and cost for each agent message in the conversation.
    Used by the Transcript dialog to display per-message costs when the switch is enabled.
    """
    from app.schemas.filter import AgentResponseLogFilter

    logs = await agent_response_log_service.get_logs_by_filter(
        AgentResponseLogFilter(conversation_id=conversation_id, node_type=None)
    )
    return [
        {
            "transcript_message_id": str(log.transcript_message_id),
            "input_tokens": log.input_tokens,
            "output_tokens": log.output_tokens,
            "total_tokens": log.total_tokens,
            "cost_usd": float(log.cost_usd) if log.cost_usd is not None else None,
        }
        for log in logs
    ]


@router.get(
    "/message/agent-response-log/{message_id}",
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Conversation.READ)),
    ],
)
async def get_agent_response_log_by_message(
    message_id: UUID,
    agent_response_log_service: AgentResponseLogService = Injected(AgentResponseLogService),
):
    """
    Return the stored agent response log associated with a given transcript (message) id.
    """
    log_entry = await agent_response_log_service.get_log_for_message(message_id)
    if not log_entry:
        raise AppException(ErrorKey.MESSAGE_NOT_FOUND, status_code=404)

    # Return a JSON-serializable view (raw_response is stored as text/json string)
    return {
        "id": str(log_entry.id),
        "conversation_id": str(log_entry.conversation_id),
        "transcript_message_id": str(log_entry.transcript_message_id),
        "raw_response": log_entry.raw_response,
        "logged_at": log_entry.logged_at.isoformat() if log_entry.logged_at else None,
        "input_tokens": log_entry.input_tokens,
        "output_tokens": log_entry.output_tokens,
        "total_tokens": log_entry.total_tokens,
        "cost_usd": float(log_entry.cost_usd) if log_entry.cost_usd is not None else None,
    }


# Legacy mode: WebSocket endpoints for backward compatibility when not using standalone WS service.
# Set VITE_WEBSOCKET_VERSION=1 to use these endpoints.
@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: UUID,
    principal: SocketPrincipal = socket_auth([P.Conversation.READ_IN_PROGRESS]),
    lang: Optional[str] = Query(default="en"),
    topics: list[str] = Query(default=["message"]),
    socket_connection_manager: SocketConnectionManager = Injected(SocketConnectionManager),
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
        logger.debug(f"WebSocket disconnected for conversation {conversation_id} (tenant: {tenant_id})")
        await socket_connection_manager.disconnect(websocket, conversation_id, tenant_id)
    except Exception as e:
        logger.exception("Unexpected WebSocket error: %s", e)
        # Attempt to disconnect even if we don't know the exact room/tenant
        try:
            await socket_connection_manager.disconnect(websocket, conversation_id, tenant_id)
        except Exception:
            # Fallback: disconnect without room info (searches all rooms)
            await socket_connection_manager.disconnect(websocket, None, None)
        await send_socket_error(websocket, ErrorKey.INTERNAL_ERROR, lang)
        await websocket.close(code=1011)


@router.websocket("/ws/dashboard/list")
async def websocket_dashboard_endpoint(
    websocket: WebSocket,
    principal: SocketPrincipal = socket_auth([P.Conversation.READ_IN_PROGRESS]),
    lang: Optional[str] = Query(default="en"),
    topics: list[str] = Query(default=["message", "update", "finalize", "hostile", "statistics"]),
    socket_connection_manager: SocketConnectionManager = Injected(SocketConnectionManager),
    dashboard_service: DashboardService = Injected(DashboardService),
):
    """
    Websocket endpoint for dashboard to receive messages from the server.
    Sends initial conversation_list on connect so the client gets current state immediately.
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

    # Send initial conversation list on connect so the client receives data immediately.
    # Use raw websocket (same as SocketConnectionManager) for reliable delivery.
    send_ws = websocket
    if hasattr(websocket, "_websocket"):
        send_ws = websocket._websocket
    try:
        from_date = datetime.now(timezone.utc) - timedelta(days=30)
        response = await dashboard_service.get_active_conversations(
            page=1, page_size=5, from_date=from_date, to_date=datetime.now(timezone.utc)
        )
        conversations = [dashboard_service.to_active_conversation_dict(c) for c in response.conversations]
        initial_msg = json.dumps(
            {"type": "conversation_list", "payload": {"conversations": conversations, "total": response.total}},
            default=str,
        )
        await send_ws.send_text(initial_msg)
        logger.info("Sent initial conversation_list to dashboard client (%d conversations)", len(conversations))
    except Exception as exc:
        logger.warning("Failed to send initial conversation_list: %s", exc)

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("Received data: %s", data)
    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for dashboard (tenant: {tenant_id})")
        await socket_connection_manager.disconnect(websocket, "DASHBOARD", tenant_id)
    except Exception as e:
        logger.exception("Unexpected WebSocket error: %s", e)
        # Attempt to disconnect even if we don't know the exact room/tenant
        try:
            await socket_connection_manager.disconnect(websocket, "DASHBOARD", tenant_id)
        except Exception:
            # Fallback: disconnect without room info (searches all rooms)
            await socket_connection_manager.disconnect(websocket, None, None)
        await send_socket_error(websocket, ErrorKey.INTERNAL_ERROR, lang)
        await websocket.close(code=1011)
