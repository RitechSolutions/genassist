import asyncio
from datetime import datetime, timezone
from uuid import UUID
from app.dependencies.injector import injector
from app.api.v1.routes.agents import run_query_agent_logic
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.modules.websockets.socket_room_enum import SocketRoomType
from app.schemas.conversation import ConversationRead
from app.schemas.conversation_transcript import (
    ConversationTranscriptCreate,
    InProgConvTranscrUpdate,
    TranscriptSegmentInput,
)
from app.db.models.conversation import ConversationModel
from app.services.agent_config import AgentConfigService
from app.services.conversations import ConversationService
from app.db.base import generate_sequential_uuid


async def process_conversation_update_with_agent(
    conversation_id: UUID,
    model: InProgConvTranscrUpdate,
    tenant_id: str,
    current_user_id: UUID,
) -> ConversationModel:
    """
    Process an in-progress conversation update with agent response handling.
    This function handles:
    - Broadcasting user messages
    - Validating conversation status
    - Generating agent responses for IN_PROGRESS conversations
    - Updating the conversation
    - Broadcasting updates and statistics

    Returns the updated conversation as ConversationModel.
    """
    service = injector.get(ConversationService)
    socket_connection_manager = injector.get(SocketConnectionManager)
    agent_config_service = injector.get(AgentConfigService)
    agent_service = injector.get(AgentConfigService)

    conversation = await service.get_conversation_by_id(conversation_id)
    if conversation.status == ConversationStatus.FINALIZED.value:
        raise AppException(ErrorKey.CONVERSATION_FINALIZED)

    if conversation.status == ConversationStatus.TAKE_OVER.value:
        if any(
            message
            for message in model.messages
            if message.speaker.lower() != "customer"
        ):
            if current_user_id != conversation.supervisor_id:
                raise AppException(ErrorKey.CONVERSATION_TAKEN_OVER_OTHER)

    # Generate IDs upfront for all incoming messages
    for message in model.messages:
        message.id = generate_sequential_uuid()

    # Broadcast user message immediately with pre-generated ID
    user_message = model.messages[0]
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="message",
            payload={
                "id": str(user_message.id),
                "create_time": user_message.create_time.isoformat() if user_message.create_time else None,
                "start_time": user_message.start_time,
                "end_time": user_message.end_time,
                "speaker": user_message.speaker,
                "text": user_message.text,
            },
            room_id=conversation_id,
            current_user_id=current_user_id,
            required_topic="message",
            tenant_id=tenant_id,
        )
    )

    if conversation.status == ConversationStatus.IN_PROGRESS.value:
        agent = await agent_config_service.get_by_user_id(current_user_id)

        session_data = {"metadata": model.metadata if model.metadata else {}}

        session_data["thread_id"] = str(conversation_id)

        if not model.metadata:
            model.metadata = {}
        model.metadata["thread_id"] = str(conversation_id)

        agent_response = await run_query_agent_logic(
            agent_service,
            str(agent.id),
            session_message=model.messages[-1].text,
            metadata=model.metadata,
        )

        agent_answer = agent_response.get("response", "No answer found")

        # Set formatted agent message in transcript
        now = datetime.now(timezone.utc)

        elapsed_seconds = (now - conversation.created_at).total_seconds()

        transcript_object = TranscriptSegmentInput(
            id=generate_sequential_uuid(),  # Generate ID upfront
            create_time=now,
            start_time=elapsed_seconds,
            end_time=elapsed_seconds,
            speaker="agent",
            text=str(agent_answer),
        )

        model.messages.append(transcript_object)

        # Broadcast agent message immediately with pre-generated ID
        _ = asyncio.create_task(
            socket_connection_manager.broadcast(
                msg_type="message",
                payload={
                    "id": str(transcript_object.id),
                    "create_time": transcript_object.create_time.isoformat() if transcript_object.create_time else None,
                    "start_time": transcript_object.start_time,
                    "end_time": transcript_object.end_time,
                    "speaker": transcript_object.speaker,
                    "text": transcript_object.text,
                },
                room_id=conversation_id,
                current_user_id=current_user_id,
                required_topic="message",
                tenant_id=tenant_id,
            )
        )

    updated_conversation = await service.update_in_progress_conversation(
        conversation_id, model
    )
    # Notify dashboard a conversation is updated
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="update",
            payload={
                "conversation_id": updated_conversation.id,
                "in_progress_hostility_score": updated_conversation.in_progress_hostility_score,
                "transcript": updated_conversation.messages[-1].text,
                "duration": updated_conversation.duration,
                "negative_reason": conversation.negative_reason,
                "topic": conversation.topic,
            },
            room_id=SocketRoomType.DASHBOARD,
            current_user_id=current_user_id,
            required_topic="hostile",
            tenant_id=tenant_id,
        )
    )

    upd_conv_pyd: ConversationRead = ConversationRead.model_validate(
        updated_conversation
    )

    # broadcast statistics
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="statistics",
            payload=upd_conv_pyd.model_dump(),
            room_id=conversation_id,
            current_user_id=current_user_id,
            required_topic="statistics",
            tenant_id=tenant_id,
        )
    )

    return updated_conversation


async def get_or_create_conversation(
    customer_id: UUID,
    operator_id: UUID,
) -> ConversationModel:
    service = injector.get(ConversationService)
    existing_conversations = await service.get_conversations_by_customer_id(
        customer_id, raise_not_found=False
    )
    open_conversations = [
        conv
        for conv in existing_conversations
        if conv.status != ConversationStatus.FINALIZED.value
    ]
    open_conversation = open_conversations[0] if open_conversations else None

    if open_conversation:
        return open_conversation
    else:
        new_conversation_model = ConversationTranscriptCreate(
            customer_id=customer_id,
            messages=[],
            operator_id=operator_id,
        )
        open_conversation = await service.start_in_progress_conversation(
            new_conversation_model
        )

    return open_conversation
