import asyncio
from datetime import datetime, timezone
import json
from typing import List
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
from app.services.file_manager import FileManagerService
from app.core.config.settings import file_storage_settings
import logging

logger = logging.getLogger(__name__)

# send message to the socket
async def send_message_to_socket(
    message: TranscriptSegmentInput,
    conversation_id: UUID,
    current_user_id: UUID,
    tenant_id: str,
) -> None:
    socket_connection_manager = injector.get(SocketConnectionManager)
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="message",
            payload={
                "id": str(message.id),
                "create_time": message.create_time.isoformat() if message.create_time else None,
                "start_time": message.start_time,
                "end_time": message.end_time,
                "speaker": message.speaker,
                "text": message.text,
                "type": message.type,
            },
            room_id=conversation_id,
            current_user_id=current_user_id,
            required_topic="message",
            tenant_id=tenant_id,
        )
    )

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
    await send_message_to_socket(user_message, conversation_id, current_user_id, tenant_id)

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
                    "type": transcript_object.type,
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

async def process_attachments_from_metadata(
    conversation_id: UUID,
    model: InProgConvTranscrUpdate,
    tenant_id: str,
    current_user_id: UUID,
    file_manager_service: FileManagerService
) -> None:
    """
    Process attachments from conversation metadata.
    Handles file retrieval, OpenAI upload, and file processing.
    """
    # Check for attachments on metadata
    if model.metadata and model.metadata.get("attachments"):
        # supported_file_extensions = ["pdf", "docx", "txt"]
        supported_file_extensions = ["pdf"]

        # process attachments
        for attachment in model.metadata.get("attachments"):
            if not attachment.get("type"):
                attachment["file_local_path"] = attachment.get("url")
                attachment["file_mime_type"] = attachment.get("mime_type")
            else:
                file_type = attachment.get("type")

                # get file by file_id
                file = await file_manager_service.get_file_by_id(attachment.get("file_id"))
                if not file:
                    pass
                else:
                    base_url = file_storage_settings.APP_URL
                    file_url = f"{base_url}/api/file-manager/files/{file.id}/source"

                    # add to attachments
                    attachment["file_local_path"] = f"{file.path}/{file.storage_path}"
                    attachment["file_mime_type"] = file.mime_type
                    
                    # Check if file has OpenAI file_id stored or upload if needed
                    if not attachment.get("openai_file_id"):
                        # Get file extension from filename or file_extension attribute
                        file_extension = ""
                        if hasattr(file, 'file_extension') and file.file_extension:
                            file_extension = file.file_extension.lower()
                        elif file.name and '.' in file.name:
                            file_extension = file.name.split('.')[-1].lower()
                        
                        # Optionally upload to OpenAI if it's a PDF, DOCX, or TXT and not already uploaded
                        if file_extension in supported_file_extensions:
                            try:
                                from app.services.open_ai_fine_tuning import OpenAIFineTuningService
                                openai_service = injector.get(OpenAIFineTuningService)
                                full_file_path = f"{file.path}/{file.storage_path}"
                                openai_file_id = await openai_service.upload_file_for_chat(
                                    file_path=full_file_path,
                                    filename=file.name,
                                    purpose="user_data"
                                )
                                attachment["openai_file_id"] = openai_file_id
                                logger.info(f"Uploaded file to OpenAI: {openai_file_id}")
                            except Exception as e:
                                logger.warning(f"Failed to upload file to OpenAI: {str(e)}")

                    # process the file upload from chat
                    await process_file_upload_from_chat(
                        conversation_id=conversation_id,
                        file_id=file.id,
                        file_url=file_url,
                        file_name=file.name,
                        file_type=file_type,
                        tenant_id=tenant_id,
                        current_user_id=current_user_id,
                    )


async def process_file_upload_from_chat(
    conversation_id: UUID,
    file_id: UUID,
    file_url: str,
    file_name: str,
    file_type: str,
    tenant_id: str,
    current_user_id: UUID,
) -> ConversationModel:
    try:
        file_data = json.dumps({
            "type": file_type,
            "url": file_url,
            "name": file_name,
        })

        message  = TranscriptSegmentInput(
            create_time=datetime.now(),
            text=file_data,
            type="file",
            speaker="user",
            # file_id=file_id,
            start_time=0.0,
            end_time=0.0,
        )

        # create the model for the conversation update
        model = InProgConvTranscrUpdate(messages=[message])

        # get the conversation
        service = injector.get(ConversationService)
        conversation = await service.get_conversation_by_id(conversation_id)
        if not conversation:
            raise AppException(ErrorKey.CONVERSATION_NOT_FOUND)

        # update the conversation with the file data
        await service.update_in_progress_conversation(conversation_id, model)

        # send the message to the socket
        await send_message_to_socket(message, conversation_id, current_user_id, tenant_id)

        return conversation        
    except Exception as e:
        logger.error(f"Error processing file upload from chat: {str(e)}")
        raise AppException(ErrorKey.ERROR_PROCESSING_FILE_UPLOAD_FROM_CHAT)