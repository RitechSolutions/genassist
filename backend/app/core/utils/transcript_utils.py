import json
from datetime import datetime
from typing import List, Optional, Set
from uuid import UUID
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
    return TranscriptMessageModel(
            conversation_id=conversation_id,
            create_time=segment.create_time,
            start_time=segment.start_time,
            end_time=segment.end_time,
            speaker=segment.speaker,
            text=segment.text,
            type=segment.type,
            sequence_number=sequence_number,
            )

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