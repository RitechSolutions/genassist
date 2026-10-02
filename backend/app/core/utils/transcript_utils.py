import json
from datetime import datetime
from typing import List, Optional, Set
from uuid import UUID
from app.core.utils.enums.transcript_message_type import TranscriptMessageType
from app.db.models.message_model import TranscriptMessageModel
from app.db.utils.sql_alchemy_utils import is_loaded
from app.schemas.conversation_transcript import TranscriptSegmentInput


def transcript_messages_to_json(
        messages: List[TranscriptMessageModel],
        exclude_fields: Optional[Set[str]] = None,
        exclude_feedback_fields: Optional[Set[str]] = None
        ) -> str:
    """
    Convert TranscriptMessageModel instances to JSON string (for backward compatibility)

    Args:
        messages: List of TranscriptMessageModel instances
        exclude_fields: Set of field names to exclude from the message level
        exclude_feedback_fields: Set of field names to exclude from feedback objects
    """
    exclude_fields = exclude_fields or set()
    exclude_feedback_fields = exclude_feedback_fields or set()

    transcript_data = []

    # Define all possible fields and their values
    field_mapping = {
        'id': lambda msg: str(msg.id),
        'create_time': lambda msg: msg.create_time.isoformat() if msg.create_time else None,
        'start_time': lambda msg: msg.start_time,
        'end_time': lambda msg: msg.end_time,
        'speaker': lambda msg: msg.speaker,
        'text': lambda msg: msg.text,
        'type': lambda msg: msg.type,
        'sequence_number': lambda msg: msg.sequence_number
        }

    for message in messages:
        segment = {}

        # Add fields that are not excluded
        for field_name, value_getter in field_mapping.items():
            if field_name not in exclude_fields:
                segment[field_name] = value_getter(message)

        # Add feedback if exists and not excluded
        if 'feedback' not in exclude_fields:
            if is_loaded(message, 'feedback') and message.feedback:
                feedback_field_mapping = {
                    'feedback': lambda fb: fb.feedback,
                    'feedback_timestamp': lambda fb: fb.feedback_timestamp.isoformat(),
                    'feedback_user_id': lambda fb: str(fb.feedback_user_id),
                    'feedback_message': lambda fb: fb.feedback_message
                    }

                segment['feedback'] = []
                for fb in message.feedback:
                    feedback_obj = {}
                    for fb_field, fb_getter in feedback_field_mapping.items():
                        if fb_field not in exclude_feedback_fields:
                            feedback_obj[fb_field] = fb_getter(fb)
                    segment['feedback'].append(feedback_obj)

        transcript_data.append(segment)

    return json.dumps(transcript_data, ensure_ascii=False)


def schema_to_transcript_message(
        segment: TranscriptSegmentInput,
        conversation_id: UUID,
        sequence_number: int
        ) -> TranscriptMessageModel:
    """
    Convert TranscriptSegmentInput schema to TranscriptMessageModel
    """
    message_data = {
        "conversation_id": conversation_id,
        "create_time": segment.create_time,
        "start_time": segment.start_time,
        "end_time": segment.end_time,
        "speaker": segment.speaker,
        "text": segment.text,
        "type": segment.type,
        "sequence_number": sequence_number,
    }

    # Include pre-generated ID if provided
    if segment.id is not None:
        message_data["id"] = segment.id

    if segment.audio_data:
        message_data["audio_data"] = segment.audio_data
        message_data["audio_format"] = segment.audio_format

    return TranscriptMessageModel(**message_data)

CUSTOMER_SPEAKERS = frozenset({"customer", "user"})
AGENT_SPEAKERS = frozenset({"agent", "assistant", "bot"})
CONVERSATIONAL_MESSAGE_TYPES = frozenset({TranscriptMessageType.MESSAGE.value, "audio"})
VOICE_MESSAGE_PLACEHOLDER = "[Voice message]"


def extract_qa_pairs(
    messages: List[TranscriptMessageModel],
) -> List[tuple[str, str]]:
    """
    Return (question, answer) pairs extracted from a conversation transcript.

    A pair is formed when a customer message is immediately followed by an
    agent message. If multiple customer messages appear before an agent
    response, only the last one is used as the question.
    """
    ordered = sorted(messages, key=lambda m: m.sequence_number)
    pairs: List[tuple[str, str]] = []
    pending_customer: str | None = None

    for msg in ordered:
        speaker = (msg.speaker or "").lower()
        if speaker in CUSTOMER_SPEAKERS:
            pending_customer = msg.text
        elif speaker in AGENT_SPEAKERS and pending_customer is not None:
            pairs.append((pending_customer, msg.text))
            pending_customer = None

    return pairs


def is_scorable_customer_message(message: TranscriptMessageModel) -> bool:
    """Real text from non-agent speakers, unknown speaker labels still get scored"""
    text = (message.text or "").strip()
    return (
        (message.type or TranscriptMessageType.MESSAGE.value) in CONVERSATIONAL_MESSAGE_TYPES
        and (message.speaker or "").strip().lower() not in AGENT_SPEAKERS
        and bool(text)
        and text != VOICE_MESSAGE_PLACEHOLDER
    )


def count_scorable_customer_messages(messages: List[TranscriptMessageModel]) -> int:
    return sum(1 for message in messages if is_scorable_customer_message(message))


def _speaker_label(speaker: Optional[str]) -> str:
    label = (speaker or "").strip().lower()
    if label in CUSTOMER_SPEAKERS:
        return "customer"
    if label in AGENT_SPEAKERS:
        return "agent"
    return label or "unknown"


def transcript_messages_to_lines(messages: List[TranscriptMessageModel], include_offset: bool = False) -> str:
    """Formats each message as speaker: text. include_offset adds [+h:mm:ss], clamped at zero"""
    first_time = next((m.create_time for m in messages if m.create_time), None) if include_offset else None
    lines = []
    for message in messages:
        text = " ".join((message.text or "").split())
        if not text:
            continue
        line = f"{_speaker_label(message.speaker)}: {text}"
        if first_time is not None and message.create_time:
            total = max(0, int((message.create_time - first_time).total_seconds()))
            hours, rest = divmod(total, 3600)
            minutes, seconds = divmod(rest, 60)
            line = f"[+{hours}:{minutes:02d}:{seconds:02d}] {line}"
        lines.append(line)
    return "\n".join(lines)


def json_to_transcript_messages(
        transcript_json: str,
        conversation_id: UUID
        ) -> List[TranscriptMessageModel]:
    """
    Convert JSON transcript string to TranscriptMessageModel instances
    """
    transcript_data = json.loads(transcript_json) if transcript_json else []
    messages = []

    for idx, segment in enumerate(transcript_data):
        message = TranscriptMessageModel(
                conversation_id=conversation_id,
                message_id=UUID(segment['message_id']),
                create_time=datetime.fromisoformat(segment['create_time'].replace('+00:00', '+00:00')),
                start_time=float(segment.get('start_time', 0)),
                end_time=float(segment.get('end_time', 0)),
                speaker=segment.get('speaker', ''),
                text=segment.get('text', ''),
                type=segment.get('type', 'message'),
                sequence_number=idx
                )
        messages.append(message)

    return messages