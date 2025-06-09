import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, WebSocket
from app.api.v1.routes.agents import run_query_agent_logic
from app.auth.dependencies import auth, permissions
from app.auth.utils import get_current_user_id
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.dependencies.ws import get_socket_connection_manager
from app.modules.websockets.handlers.in_progress_conversation_handler import handle_conversation_socket
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.schemas.agent import AgentRead
from app.schemas.conversation import ConversationRead
from app.schemas.conversation_transcript import ConversationTranscriptCreate, InProgConvTranscrUpdate, \
    InProgressConversationTranscriptFinalize, TranscriptSegmentInput
from app.schemas.filter import ConversationFilter
from app.services.agent_config import AgentConfigService
from app.services.auth import AuthService
from app.services.conversations import ConversationService


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{conversation_id}", response_model=ConversationRead, dependencies=[
    Depends(auth),
    Depends(permissions("read:conversation"))
    ])
async def get(conversation_id: UUID, service: ConversationService = Depends()):
    return await service.get_conversation_by_id_full(conversation_id)


@router.post("/in-progress/start", dependencies=[
    Depends(auth),
    Depends(permissions("create:in_progress_conversation"))
    ])
async def start(
        model: ConversationTranscriptCreate,
        service: ConversationService = Depends(),
        agent_config_service: AgentConfigService = Depends(),
        ):
    """
    Create a new in-progress conversation and store the partial transcript.
    """
    if model.messages:
        raise AppException(error_key=ErrorKey.CONVERSATION_MUST_START_EMPTY, status_code=400)
    userid = get_current_user_id()
    logger.debug("userid:"+str(userid))

    agent = await agent_config_service.get_by_user_id(userid)
    if not agent:
        logger.debug("agent not found")
    else:
        logger.debug("agent:"+agent.name)

    agent_read = AgentRead.model_validate(agent)
    model.operator_id = agent.operator_id
    conversation = await service.start_in_progress_conversation(model)
    return {"message": "Conversation started", "conversation_id": conversation.id, "agent_welcome_message":
        agent_read.welcome_message, "agent_possible_queries": agent_read.possible_queries}


@router.patch("/in-progress/update/{conversation_id}", dependencies=[
    Depends(auth),
    Depends(permissions("update:in_progress_conversation"))
    ])
async def update(
        conversation_id: UUID,
        model: InProgConvTranscrUpdate,
        service: ConversationService = Depends(),
        socket_connection_manager: SocketConnectionManager = Depends(get_socket_connection_manager),
        agent_config_service: AgentConfigService = Depends(),
        ):
    """
    Append segments to an existing in-progress conversation.
    """

    transcript_json = [segment.model_dump() for segment in model.messages]

    asyncio.create_task(socket_connection_manager.broadcast(msg_type="message", payload=transcript_json[0],
                                                            conversation_id=conversation_id,
                                                            current_user_id=get_current_user_id(),
                                                            required_topic="message"))


    conversation = await service.get_conversation_by_id(conversation_id)
    if conversation.status == ConversationStatus.FINALIZED.value:
        raise AppException(ErrorKey.CONVERSATION_TAKEN_OVER)

    if conversation.status == ConversationStatus.IN_PROGRESS.value:
        agent = await agent_config_service.get_by_user_id(get_current_user_id())
        agent_response = await run_query_agent_logic(
                str(agent.id),
                user_query=model.messages[-1].text,
                metadata={"thread_id": str(conversation_id)}
                )
        agent_answer = agent_response.get("response",
                                          "No answer found")

        # Set formatted agent message in transcript
        now = datetime.now(timezone.utc)

        elapsed_seconds = (now - conversation.created_at).total_seconds()

        transcript_object = TranscriptSegmentInput(
                create_time=now,
                start_time=elapsed_seconds,
                end_time=elapsed_seconds,
                speaker="agent",
                text=agent_answer
                )

        model.messages.append(transcript_object)

        asyncio.create_task(socket_connection_manager.broadcast(msg_type="message",
                                                                payload=transcript_object.model_dump(),
                                                                conversation_id=conversation_id,
                                                                current_user_id=get_current_user_id(),
                                                                required_topic="message"))



    updated_conversation =  await service.update_in_progress_conversation(conversation_id, model)
    upd_conv_pyd = ConversationRead.model_validate(updated_conversation)

    # broadcast statistics
    asyncio.create_task(socket_connection_manager.broadcast(msg_type="statistics",
                                                            payload=upd_conv_pyd.model_dump(),
                                                            conversation_id=conversation_id,
                                                            current_user_id=get_current_user_id(),
                                                            required_topic="statistics"))

    return updated_conversation

@router.patch("/in-progress/finalize/{conversation_id}", dependencies=[
    Depends(auth),
    Depends(permissions("update:in_progress_conversation"))
    ])
async def finalize(
        conversation_id: UUID,
        finalize: InProgressConversationTranscriptFinalize,
        service: ConversationService = Depends(),
        socket_connection_manager: SocketConnectionManager = Depends(get_socket_connection_manager)
        ):
    """
    Finalize the conversation so that no more partial updates are allowed.
    Optionally trigger the final analysis or let another endpoint handle it.
    """
    asyncio.create_task(socket_connection_manager.broadcast(msg_type="finalize",
                                                            conversation_id=conversation_id,
                                                            current_user_id=get_current_user_id(),
                                                            required_topic="finalize"))

    finalized_conversation_analysis = await service.finalize_in_progress_conversation(finalize.llm_analyst_id,
                                                                                conversation_id)
    return finalized_conversation_analysis

@router.patch("/in-progress/takeover-super/{conversation_id}", dependencies=[
    Depends(auth),
    Depends(permissions("takeover_in_progress_conversation"))
    ])
async def takeover_supervisor(
        conversation_id: UUID,
        service: ConversationService = Depends(),
        socket_connection_manager: SocketConnectionManager = Depends(get_socket_connection_manager)
        ):
    """
        Take over conversation from agent by a supervisor.
    """
    conversation_taken_over =  await service.supervisor_takeover_conversation(conversation_id)
    asyncio.create_task(socket_connection_manager.broadcast(msg_type="takeover",
                                              conversation_id=conversation_taken_over.id,
                                              current_user_id=get_current_user_id(),
                                              required_topic="takeover"))
    return conversation_taken_over

@router.get("/", response_model=list[ConversationRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:conversation"))
    ])
async def get(conversation_filter: ConversationFilter = Depends(),
                            conversations_service: ConversationService = Depends()):
    return await conversations_service.get_conversations(conversation_filter)


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        conversation_id: UUID,
        access_token: str = Query(default=None),
        api_key: str = Query(default=None),
        lang: Optional[str] = Query(default="en"),
        auth_service: AuthService = Depends(),
        topics: list[str] = Query(default=["message"]),
        socket_connection_manager: SocketConnectionManager = Depends(get_socket_connection_manager),
        ):
    await handle_conversation_socket(
            websocket=websocket,
            conversation_id=conversation_id,
            access_token=access_token,
            api_key=api_key,
            lang=lang,
            auth_service=auth_service,
            socket_connection_manager=socket_connection_manager,
            topics=topics,
            )
