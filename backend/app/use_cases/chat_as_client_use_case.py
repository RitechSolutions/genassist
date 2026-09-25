import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from app.api.v1.routes.agents import run_query_agent_logic
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.db_connection_utils import release_db_connection
from app.core.utils.enums.conversation_status_enum import ConversationStatus
from app.db.base import generate_sequential_uuid
from app.db.models.conversation import ConversationModel
from app.dependencies.injector import injector
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.core.tenant_scope import get_tenant_context
from app.schemas.conversation import ConversationRead
from app.schemas.conversation_transcript import (
    ConversationTranscriptCreate,
    InProgConvTranscrUpdate,
    TranscriptSegmentInput,
)
from app.services.agent_config import AgentConfigService
from app.services.agent_response_log import AgentResponseLogService
from app.services.analytics_realtime import update_stats_incrementally
from app.services.conversations import ConversationService
from app.services.translations import TranslationsService
from app.core.utils.custom_attributes import extract_custom_attributes, get_hidden_keys
from app.core.utils.sensitive_data_utils import build_hidden_value_map, mask_hidden_values
from app.modules.workflow.engine.pii_anonymizer import PIIAnonymizer
from app.services.file_manager import FileManagerService
from app.services.realtime_notifications import (
    emit_notification,
    conversation_started_notification_description,
    notification_payload,
    transcript_conversation_notification_url,
)

logger = logging.getLogger(__name__)

_pii_redactor = PIIAnonymizer(entities=["CREDIT_CARD", "IBAN_CODE", "US_SSN"])

# Base instruction used when an agent greets the visitor on conversation start. The agent's
# optional `greeting_prompt` is appended to extend (not replace) it. The reply language is
# stated explicitly below (there is no visitor message yet to infer it from).
DEFAULT_GREETING_PROMPT = (
    "You are starting a new conversation with a user who has just opened the chat. "
    "Greet them warmly and briefly, in one or two short sentences, and invite them to ask "
    "their question or tell you what they need. Do not make up details about the user; "
    "do not ask for information unless the workflow requires it."
)

# Display names for the languages the platform seeds/supports, so the greeting instruction
# can name the target language instead of passing a bare code the model may misread.
_LANGUAGE_DISPLAY_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "pt": "Portuguese", "it": "Italian", "zh": "Chinese", "ar": "Arabic", "sq": "Albanian",
}


async def _build_start_greeting_message(agent, language: Optional[str]) -> str:
    """Greeting instruction sent (invisibly) to the workflow on conversation start.

    Combines the default prompt with the agent's optional `greeting_prompt` (resolved to the
    conversation language if a translation exists), then states the reply language explicitly
    — at conversation open there is no visitor message for the model to infer language from.
    """
    extension = (getattr(agent, "greeting_prompt", None) or "").strip()
    if extension and language:
        key = f"agent.{agent.id}.greeting_prompt"
        try:
            translations_service = injector.get(TranslationsService)
            resolved = await translations_service.resolve_many_for_lang({key: extension}, language)
            extension = (resolved.get(key) or extension).strip()
        except Exception as exc:  # translation is best-effort; fall back to the source text
            logger.debug("greeting_prompt translation lookup failed: %s", exc)

    parts = [DEFAULT_GREETING_PROMPT]
    if extension:
        parts.append(extension)
    if language:
        code = str(language).split("-")[0].lower()
        name = _LANGUAGE_DISPLAY_NAMES.get(code, code)
        parts.append(f"Write your greeting in {name}.")
    return "\n\n".join(parts)


# send message to the socket
async def send_message_to_socket(
    message: TranscriptSegmentInput,
    conversation_id: UUID,
    current_user_id: UUID,
    tenant_id: str,
) -> None:
    socket_connection_manager = injector.get(SocketConnectionManager)
    payload = {
        "id": str(message.id),
        "create_time": message.create_time.isoformat() if message.create_time else None,
        "start_time": message.start_time,
        "end_time": message.end_time,
        "speaker": message.speaker,
        "text": message.text,
        "type": message.type,
    }
    if message.audio_format:
        payload["audio_format"] = message.audio_format
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="message",
            payload=payload,
            room_id=conversation_id,
            current_user_id=current_user_id,
            required_topic="message",
            tenant_id=tenant_id,
        )
    )


def _extract_spoken_text(agent_response: dict) -> str:
    """Extract the text the LLM generated before TTS converted it to audio."""
    try:
        raw = agent_response.get("row_agent_response", {})
        state = raw.get("state", {})
        node_status = state.get("nodeExecutionStatus", {})

        # First pass: look for LLM / agent node outputs (most reliable)
        for node_id, status in node_status.items():
            node_type = status.get("type", "")
            if node_type in ("llmModelNode", "agentNode", "voiceAgentNode"):
                output = status.get("output")
                if isinstance(output, dict):
                    text = output.get("message", "") or output.get("response", "")
                    if text:
                        return text
                if isinstance(output, str) and output:
                    return output

        # Second pass: find any non-audio, non-error string output (fallback)
        for node_id, status in node_status.items():
            node_type = status.get("type", "")
            if node_type in ("ttsNode", "sttNode", "chatInputNode", "chatOutputNode"):
                continue
            output = status.get("output")
            if isinstance(output, str) and output and not output.startswith("Error"):
                return output

        logger.debug(
            "Could not extract spoken text from workflow. Node types present: %s",
            [s.get("type") for s in node_status.values()],
        )
    except Exception as exc:
        logger.warning("_extract_spoken_text failed: %s", exc)
    return ""


def _build_agent_segment(
    now: datetime, elapsed_seconds: float, text: str, **extra: Any
) -> TranscriptSegmentInput:
    """Build an agent-authored transcript segment with shared id/timing fields."""
    return TranscriptSegmentInput(
        id=generate_sequential_uuid(),
        create_time=now,
        start_time=elapsed_seconds,
        end_time=elapsed_seconds,
        speaker="agent",
        text=text,
        **extra,
    )


def _agent_text_from_answer(agent_answer: Any) -> str:
    """Displayable text for a plain answer, which may be a string or a
    {"message"/"response", ...} dict — avoids stringifying the whole dict into the chat."""
    if isinstance(agent_answer, dict):
        return agent_answer.get("message") or agent_answer.get("response") or str(agent_answer)
    return str(agent_answer)


def _build_agent_transcript_segment(
    agent_response: dict,
    metadata: Optional[dict],
    now: datetime,
    elapsed_seconds: float,
) -> TranscriptSegmentInput:
    """Turn an agent run result into the agent transcript segment to persist/broadcast.

    Picks the segment shape from what the workflow returned (first match wins):
      - awaiting_input -> form_request segment carrying the form schema
      - live_result    -> live-voice reply (authoritative text carried in metadata; the
                          DAG output can be a raw/stringified dict depending on which
                          node finishes last, so we don't trust it here)
      - nested audio   -> voice agent reply (text + audio payload)
      - typed audio    -> audio response from a TTS workflow
      - otherwise      -> plain text (extracting message/response from a dict answer)
    """
    if agent_response.get("status") == "awaiting_input":
        response_output = agent_response.get("response", {})
        form_schema = response_output.get("form_schema", {}) if isinstance(response_output, dict) else {}
        return _build_agent_segment(now, elapsed_seconds, json.dumps(form_schema), type="form_request")

    live_result = (metadata or {}).get("live_result")
    if isinstance(live_result, dict) and live_result.get("message"):
        return _build_agent_segment(now, elapsed_seconds, str(live_result["message"]))

    agent_answer = agent_response.get("response", "No answer found")

    if (
        isinstance(agent_answer, dict)
        and isinstance(agent_answer.get("audio"), dict)
        and agent_answer["audio"].get("type") == "audio"
    ):
        audio = agent_answer["audio"]
        return _build_agent_segment(
            now,
            elapsed_seconds,
            str(agent_answer.get("message") or "[Audio response]"),
            type="audio",
            audio_data=base64.b64decode(audio.get("data", "")),
            audio_format=audio.get("format", "wav"),
        )

    if isinstance(agent_answer, dict) and agent_answer.get("type") == "audio":
        return _build_agent_segment(
            now,
            elapsed_seconds,
            _extract_spoken_text(agent_response) or "[Audio response]",
            type="audio",
            audio_data=base64.b64decode(agent_answer.get("data", "")),
            audio_format=agent_answer.get("format", "mp3"),
        )

    return _build_agent_segment(now, elapsed_seconds, _agent_text_from_answer(agent_answer))


async def _localize_form_schema(agent_response: dict, agent_id: Any, language: Optional[str]) -> None:
    """Translate a Human In The Loop form's user-facing strings into the conversation
    language, in place. No-op unless the workflow paused with a form_schema.

    Mirrors agent-field translation: keys are `agent.{agent_id}.node.{node_id}.*`, resolved
    with the same fallback chain (language -> stored default -> source English). The chat
    plugin renders whatever labels it receives, so resolving here keeps it untouched.
    """
    if agent_response.get("status") != "awaiting_input":
        return
    response_output = agent_response.get("response")
    if not isinstance(response_output, dict):
        return
    form_schema = response_output.get("form_schema")
    if not isinstance(form_schema, dict):
        return
    node_id = form_schema.get("node_id")
    if not node_id:
        return

    prefix = f"agent.{agent_id}.node.{node_id}"
    fields = [f for f in (form_schema.get("fields") or []) if isinstance(f, dict)]

    # Collect every translatable string -> its source value (the resolver's fallback).
    items: dict[str, Optional[str]] = {}
    message_key = f"{prefix}.message"
    if form_schema.get("message"):
        items[message_key] = form_schema.get("message")
    for field in fields:
        fname = field.get("name")
        if not fname:
            continue
        fkey = f"{prefix}.fields.{fname}"
        for attr in ("label", "placeholder", "description"):
            if field.get(attr):
                items[f"{fkey}.{attr}"] = field.get(attr)
        for opt in (field.get("options") or []):
            if isinstance(opt, dict) and opt.get("value") and opt.get("label"):
                items[f"{fkey}.options.{opt['value']}.label"] = opt.get("label")

    if not items:
        return

    translations_service = injector.get(TranslationsService)
    resolved = await translations_service.resolve_many_for_lang(items, language)

    # Apply resolved values back (fall back to the original if a key wasn't resolved).
    if message_key in items:
        form_schema["message"] = resolved.get(message_key) or form_schema.get("message")
    for field in fields:
        fname = field.get("name")
        if not fname:
            continue
        fkey = f"{prefix}.fields.{fname}"
        for attr in ("label", "placeholder", "description"):
            akey = f"{fkey}.{attr}"
            if akey in items:
                field[attr] = resolved.get(akey) or field.get(attr)
        for opt in (field.get("options") or []):
            if isinstance(opt, dict) and opt.get("value"):
                okey = f"{fkey}.options.{opt['value']}.label"
                if okey in items:
                    opt["label"] = resolved.get(okey) or opt.get("label")


async def process_conversation_update_with_agent(
    conversation_id: UUID,
    model: InProgConvTranscrUpdate,
    tenant_id: str,
    current_user_id: UUID,
    audio_bytes: Optional[bytes] = None,
    audio_format: Optional[str] = None,
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
    agent_response_log_service = injector.get(AgentResponseLogService)

    conversation = await service.get_conversation_by_id(conversation_id)
    if conversation.status == ConversationStatus.FINALIZED.value:
        raise AppException(ErrorKey.CONVERSATION_FINALIZED)

    if conversation.status == ConversationStatus.TAKE_OVER.value:
        if any(message for message in model.messages if message.speaker.lower() != "customer"):
            if current_user_id != conversation.supervisor_id:
                raise AppException(ErrorKey.CONVERSATION_TAKEN_OVER_OTHER)

    # Generate IDs and redact cardholder data before any downstream
    # consumer (WebSocket, LLM, database, logs) sees the raw text.
    for message in model.messages:
        message.id = generate_sequential_uuid()
        if message.text:
            message.text = _pii_redactor.redact(message.text)

    # A start trigger is an invisible message the chat plugin sends right after the
    # conversation opens (when the agent's greet_on_start is enabled). It runs the workflow
    # with a greeting instruction so the agent greets the visitor — and if a Human In The
    # Loop node is wired right after Chat Input, it pauses and shows its form instead. The
    # trigger itself is never shown to the visitor nor kept in the transcript; only the
    # resulting agent reply (greeting or form) is broadcast/persisted.
    is_start_form_trigger = bool(model.metadata and model.metadata.get("start_form_trigger"))

    # Tag user message with audio data if present
    user_message = model.messages[0]
    if audio_bytes:
        user_message.audio_data = audio_bytes
        user_message.audio_format = audio_format or "webm"
        user_message.type = "audio"
        if not user_message.text or user_message.text.strip() == "":
            user_message.text = "[Voice message]"

    # 1:1 chat: broadcast user message immediately with pre-generated ID
    if not is_start_form_trigger:
        await send_message_to_socket(user_message, conversation_id, current_user_id, tenant_id)

    if conversation.status == ConversationStatus.IN_PROGRESS.value:
        agent = await agent_config_service.get_by_user_id(current_user_id, with_workflow=True)

        session_data = {"metadata": model.metadata if model.metadata else {}}
        session_data["thread_id"] = str(conversation_id)

        if not model.metadata:
            model.metadata = {}

        model.metadata["thread_id"] = str(conversation_id)

        # Inject audio data into metadata for the workflow engine (base64, in-memory only)
        if audio_bytes:
            model.metadata["audio_data"] = base64.b64encode(audio_bytes).decode("utf-8")
            model.metadata["audio_format"] = audio_format or "webm"

        # On a start trigger, feed the workflow the greeting instruction (default + the
        # agent's optional extension, in the conversation language) so the agent greets;
        # don't persist it to chat memory.
        if is_start_form_trigger:
            session_message = await _build_start_greeting_message(
                agent, (model.metadata or {}).get("language")
            )
        else:
            session_message = model.messages[-1].text

        # Release the pooled connection before the LLM/tool run so it isn't held
        # idle-in-transaction for the duration of the call (see incident-queuepool-exhaustion.md).
        await release_db_connection(context=f"conversation {conversation_id}")

        agent_response = await run_query_agent_logic(
            agent_service,
            str(agent.id),
            session_message=session_message,
            metadata=model.metadata,
            persist=not is_start_form_trigger,
        )

        # Translate a Human In The Loop form to the conversation language (no-op for any
        # other response) so its labels match the agent's other translated content.
        await _localize_form_schema(
            agent_response, agent.id, (model.metadata or {}).get("language")
        )

        # Mask any Chat Input parameters marked "hidden" before the agent response
        # and messages are persisted/logged. The workflow already executed with the
        # real values (and Redis functional stores already hold them), so this only
        # affects stored/displayed data: agent_response_logs.raw_response,
        # transcript_messages.text, and conversations.custom_attributes.
        hidden_keys = get_hidden_keys(agent.workflow.get("nodes") if agent.workflow else None)
        if hidden_keys:
            node_statuses = (
                agent_response.get("row_agent_response", {})
                .get("state", {})
                .get("nodeExecutionStatus", {})
            )
            hidden_value_map = build_hidden_value_map(
                hidden_keys,
                node_statuses=node_statuses,
                fallback_values=model.metadata,
            )
            if hidden_value_map:
                agent_response = mask_hidden_values(agent_response, hidden_value_map)
                for msg in model.messages:
                    if msg.text:
                        msg.text = mask_hidden_values(msg.text, hidden_value_map)

        # Set formatted agent message in transcript
        now = datetime.now(timezone.utc)
        elapsed_seconds = (now - conversation.created_at).total_seconds()

        transcript_object = _build_agent_transcript_segment(
            agent_response, model.metadata, now, elapsed_seconds
        )

        # For a start-form trigger, drop the invisible trigger message so only the form
        # (agent reply) is persisted; otherwise keep both the user message and the reply.
        if is_start_form_trigger:
            model.messages = [transcript_object]
        else:
            model.messages.append(transcript_object)

        # 1:1 chat: broadcast agent message immediately with pre-generated ID
        await send_message_to_socket(transcript_object, conversation_id, current_user_id, tenant_id)

    previous_hostility_score = int(conversation.in_progress_hostility_score or 0)

    # update the conversation with the new messages
    updated_conversation = await service.update_in_progress_conversation(conversation_id, model)

    # After messages are persisted, log the full agent response tied to the stored message id.
    if conversation.status == ConversationStatus.IN_PROGRESS.value:
        try:
            # The newest message should be the agent reply we just appended
            last_message = updated_conversation.messages[-1] if updated_conversation.messages else None
            if last_message:
                await agent_response_log_service.log_response_for_message(
                    conversation_id=updated_conversation.id,
                    transcript_message_id=last_message.id,
                    agent_response=agent_response,
                    workflow_execution_id=agent_response.get("row_agent_response", {}).get("execution_id"),
                )
                # Fire incremental analytics update in background
                _ = asyncio.create_task(update_stats_incrementally(agent_response))
        except Exception as e:
            logger.warning(f"Failed to persist AgentResponseLog after update: {e}", exc_info=True)

    # 1:1 chat: notify dashboard a conversation is updated
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
                "create_time": updated_conversation.created_at.isoformat() if updated_conversation.created_at else None,
            },
            room_id="DASHBOARD",
            current_user_id=current_user_id,
            required_topic="update",
            tenant_id=tenant_id,
        )
    )

    current_hostility_score = int(updated_conversation.in_progress_hostility_score or 0)
    if previous_hostility_score <= 50 < current_hostility_score:
        emit_notification(
            socket_connection_manager=socket_connection_manager,
            tenant_id=tenant_id,
            current_user_id=current_user_id,
            payload=notification_payload(
                notification_id=f"conversation_hostility:{updated_conversation.id}",
                title="High Hostility Detected",
                description=(
                    f"Conversation {str(updated_conversation.id)[:8]}... reached hostility score "
                    f"{current_hostility_score}%."
                ),
                level="warning",
                action_url=transcript_conversation_notification_url(updated_conversation.id),
                timestamp=updated_conversation.updated_at,
                group_id=getattr(updated_conversation, "group_id", None),
                entity_kind="conversation",
                entity_id=updated_conversation.id,
                event_key=f"conversation_hostility:{updated_conversation.id}",
            ),
        )

    upd_conv_pyd: ConversationRead = ConversationRead.model_validate(updated_conversation)

    # 1:1 chat: broadcast statistics
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

    # Persist custom workflow attributes
    if conversation.status == ConversationStatus.IN_PROGRESS.value:
        await _persist_custom_attributes(
            service, agent, agent_response, updated_conversation
        )

    # return the updated conversation
    return updated_conversation


async def _persist_custom_attributes(
    service: ConversationService,
    agent,
    agent_response: dict,
    conversation: ConversationModel,
) -> None:
    """Extract filterable workflow attributes and store them on the conversation."""
    try:
        workflow_nodes = agent.workflow.get("nodes") if agent.workflow else None
        new_attrs = extract_custom_attributes(agent_response, workflow_nodes=workflow_nodes)
        if new_attrs:
            existing = conversation.custom_attributes or {}
            existing.update(new_attrs)
            await service.update_custom_attributes(conversation.id, existing)
            conversation.custom_attributes = existing
    except Exception as e:
        logger.warning(f"Failed to persist custom_attributes: {e}")


async def get_or_create_conversation(
    customer_id: UUID,
    operator_id: UUID,
) -> ConversationModel:
    service = injector.get(ConversationService)
    existing_conversations = await service.get_conversations_by_customer_id(customer_id, raise_not_found=False)
    open_conversations = [conv for conv in existing_conversations if conv.status != ConversationStatus.FINALIZED.value]
    open_conversation = open_conversations[0] if open_conversations else None

    if open_conversation:
        return open_conversation
    else:
        new_conversation_model = ConversationTranscriptCreate(
            customer_id=customer_id,
            messages=[],
            operator_id=operator_id,
        )
        open_conversation = await service.start_in_progress_conversation(new_conversation_model)
        emit_notification(
            socket_connection_manager=injector.get(SocketConnectionManager),
            tenant_id=get_tenant_context(),
            payload=notification_payload(
                notification_id=f"conversation_started:{open_conversation.id}",
                title="Conversation Started",
                description=conversation_started_notification_description(
                    open_conversation.id
                ),
                level="info",
                action_url=transcript_conversation_notification_url(open_conversation.id),
                timestamp=open_conversation.created_at,
                group_id=getattr(open_conversation, "group_id", None),
                entity_kind="conversation",
                entity_id=open_conversation.id,
                event_key=f"conversation_started:{open_conversation.id}",
            ),
        )

    return open_conversation


async def process_attachments_from_metadata(
    base_url: str,
    conversation_id: UUID,
    model: InProgConvTranscrUpdate,
    tenant_id: str,
    current_user_id: UUID,
    file_manager_service: FileManagerService,
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
                    # get the file url for local storage provider missing the base url
                    file_url = await file_manager_service.get_file_url(file)
                    chat_file_url = file_url

                    # add to attachments local path when the storage provider is local
                    if file.storage_provider == "local":
                        chat_file_url = f"{base_url}{file_url.rstrip('/')}"
                        attachment["file_local_path"] = f"{file.storage_path}/{file.path}"

                    attachment["file_url"] = chat_file_url
                    attachment["file_mime_type"] = file.mime_type
                    attachment["file_storage_provider"] = file.storage_provider

                    # Check if file has OpenAI file_id stored or upload if needed
                    if not attachment.get("openai_file_id"):
                        # Get file extension from filename or file_extension attribute
                        file_extension = ""
                        if hasattr(file, "file_extension") and file.file_extension:
                            file_extension = file.file_extension.lower()
                        elif file.name and "." in file.name:
                            file_extension = file.name.split(".")[-1].lower()

                        # Optionally upload to OpenAI if it's a PDF, DOCX, or TXT and not already uploaded
                        if file_extension in supported_file_extensions:
                            try:
                                from app.services.open_ai_fine_tuning import OpenAIFineTuningService

                                openai_service = injector.get(OpenAIFineTuningService)
                                openai_file_id = await openai_service.upload_file_for_chat(
                                    file_url=chat_file_url, filename=file.name, purpose="user_data"
                                )
                                attachment["openai_file_id"] = openai_file_id
                                logger.info(f"Uploaded file to OpenAI: {openai_file_id}")
                            except Exception as e:
                                logger.warning(f"Failed to upload file to OpenAI: {str(e)}")

                    # process the file upload from chat
                    await process_file_upload_from_chat(
                        conversation_id=conversation_id,
                        file_id=file.id,
                        file_url=chat_file_url,
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
        file_data = json.dumps(
            {
                "type": file_type,
                "url": file_url,
                "name": file_name,
                "file_id": str(file_id),
            }
        )

        message = TranscriptSegmentInput(
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
