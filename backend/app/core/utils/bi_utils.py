from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from fastapi import UploadFile
from typing import Tuple
from app.core.config.settings import settings
from app.db.models import ConversationModel
from app.schemas.conversation_transcript import TranscriptSegmentInput


def update_agent_average_sentiment(agent_data, negative_sentiment, neutral_sentiment, positive_sentiment):
    # Calculate and update average sentiment percentages
    if "averageSentiment" not in agent_data:
        agent_data["averageSentiment"] = {
            "positive": positive_sentiment,
            "neutral": neutral_sentiment,
            "negative": negative_sentiment
        }
    else:
        agent_data["averageSentiment"]["positive"] = (
                (agent_data["averageSentiment"]["positive"] * (agent_data["callCount"] - 1) + positive_sentiment) /
                agent_data["callCount"]
        )
        agent_data["averageSentiment"]["neutral"] = (
                (agent_data["averageSentiment"]["neutral"] * (agent_data["callCount"] - 1) + neutral_sentiment) /
                agent_data["callCount"]
        )
        agent_data["averageSentiment"]["negative"] = (
                (agent_data["averageSentiment"]["negative"] * (agent_data["callCount"] - 1) + negative_sentiment) /
                agent_data["callCount"]
        )
    # Round the averages to 2 decimal places
    agent_data["averageSentiment"] = {k: round(v, 2) for k, v in agent_data["averageSentiment"].items()}


import re


def update_transcript_with_roles(transcript_data, customer_speaker_info):
    # Extract customer speaker using regex
    match = re.search(r'(SPEAKER_\d+)', customer_speaker_info)
    if not match:
        return transcript_data  # No change if customer speaker info is not found

    customer_speaker = match.group(1)
    speakers = {customer_speaker: 'Customer'}

    # Identify the other speaker(s) as 'Agent'
    for segment in transcript_data:
        if segment.speaker != customer_speaker:
            speakers[segment.speaker] = 'Agent'

    # Update transcript with 'Customer' and 'Agent'
    updated_transcript = [
        {
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "speaker": speakers[segment.speaker],
            "text": segment.text,
        }
        for segment in transcript_data
    ]

    return updated_transcript

def update_transcript_with_roles_no_audio(transcript_data, customer_speaker_info):
    # Extract customer speaker using regex
    match = re.search(r'(SPEAKER_\d+)', customer_speaker_info)
    if not match:
        return transcript_data  # No change if customer speaker info is not found

    customer_speaker = match.group(1)
    speakers = {customer_speaker: 'Customer'}

    # Identify the other speaker(s) as 'Agent'
    for segment in transcript_data:
        if segment.speaker != customer_speaker:
            speakers[segment.speaker] = 'Agent'

    # Update transcript with 'Customer' and 'Agent'
    updated_transcript = [
        {
            "start_time": segment.start_time,
            "end_time": segment.end_time,
            "speaker": speakers[segment.speaker],
            "text": segment.text,
            "create_time": segment.create_time,
        }
        for segment in transcript_data
    ]

    return updated_transcript

def normalize_to_range(x, min_val, max_val):
    # Normalize the value
    normalized = 1 + ((x - min_val) / (max_val - min_val)) * (5 - 1)
    # Round to 1 decimal place
    return normalized

def calculate_rating_score(positive_percentage, neutral_percentage, negative_percentage):
    # Assign scores to each rating type
    positive_score = 5
    neutral_score = 3
    negative_score = 1

    # Convert percentages to proportions
    positive = positive_percentage / 100
    neutral = neutral_percentage / 100
    negative = negative_percentage / 100

    # Calculate the weighted average score
    score = (positive * positive_score) + (neutral * neutral_score) + (negative * negative_score)

    # Normalize to range 1 to 5
    normalize_to_range(score, 1, 5)
    return round(score, 1)


def calculate_duration_from_transcript(transcript_data: list[TranscriptSegmentInput]) -> int:
    """
    Calculate the duration of the transcript based on the difference between
    the first and last 'start_time' values.

    Args:
    - transcript_data (list): List of transcript segments containing 'start_time'.

    Returns:
    - duration (int): The difference between the first and last 'end_time' in seconds.
    """
    if not transcript_data or len(transcript_data) < 2:
        return 0

    # Extract the first and last create_time values
    first_start_time = transcript_data[0].start_time
    last_end_time = transcript_data[-1].end_time

    # Calculate the duration
    duration = last_end_time - first_start_time
    return int(duration)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in settings.SUPPORTED_AUDIO_FORMATS


def extract_transcript_from_whisper_model(transcription_object):

    # TODO Check why it fails without if in seed method
    if not transcription_object or "segments" not  in transcription_object:
        return []
    transcript_data = [{
        'start_time': segment['start'],
        'end_time': segment['end'],
        'text': segment['text']
    }
        for segment in transcription_object['segments']
    ]
    return transcript_data


async def validate_upload_file_size(file: UploadFile, max_size: int = settings.MAX_CONTENT_LENGTH) -> int:
    """Validate the file size by reading it in chunks.
    Raises 413 if file is too large. Returns the total size in bytes.
    Resets the stream position to the start.
    """
    size = 0
    CHUNK_SIZE = 1024 * 1024  # 1MB

    while chunk := await file.read(CHUNK_SIZE):
        size += len(chunk)
        if size > max_size:
            raise AppException(error_key=ErrorKey.FILE_SIZE_TOO_LARGE)

    await file.seek(0)  # Reset the stream so you can still read the file
    return size


def calculate_word_count(transcript_segments: list[TranscriptSegmentInput], target: str)-> int:
    return sum(
            len(seg.text.split()) for seg in transcript_segments if seg.speaker.lower() == target)


def calculate_speaker_ratio_from_segments(transcript_segments: list[TranscriptSegmentInput])-> Tuple[int, int, int]:
    customer_word_count = calculate_word_count(transcript_segments, target="customer")
    agent_word_count = calculate_word_count(transcript_segments, target="agent")
    total_word_count = customer_word_count + agent_word_count
    if total_word_count == 0:
        customer_ratio = agent_ratio = 0
    else:
        customer_ratio = round((customer_word_count / total_word_count) * 100)
        agent_ratio = 100 - customer_ratio  # Ensures total is 100
    return agent_ratio, customer_ratio, total_word_count


def clean_gpt_json_response(response_text: str) -> str:
    """
    Removes markdown formatting like triple backticks and 'json' labels.
    """
    response_text = response_text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    elif response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    return response_text.strip()


def filter_conversation_date(conversation_filter, query):
    if conversation_filter.from_date:
        query = query.where(ConversationModel.conversation_date >= conversation_filter.from_date)
    if conversation_filter.to_date:
        query = query.where(ConversationModel.conversation_date <= conversation_filter.to_date)
<<<<<<< HEAD
    return query
=======
    return query


def get_masked_api_key(api_key):
    return api_key[:3] + "***" + api_key[-3:]
>>>>>>> development
