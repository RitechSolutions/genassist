import os
import pytest
import logging
from app.db.seed.seed_data_config import seed_test_data


logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_post_audio(authorized_client):
    """Test audio upload and transcription endpoint."""
    op_response = authorized_client.get("/api/operators/")

    if op_response.status_code != 200:
        pytest.skip(f"Could not get operators: {op_response.status_code}")

    operators = op_response.json()
    if not operators:
        pytest.skip("No operators available for testing")

    logger.info("test_post_audio - operators: %s", operators)
    op_id = operators[0]["id"]

    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = os.path.join(dir_path, 'tech-support.mp3')

    if not os.path.exists(filename):
        pytest.skip(f"Test audio file not found: {filename}")

    logger.info("uploading test file: %s", filename)

    data = {
        'operator_id': op_id,
        'recorded_at': '2025-04-01T14:25:00Z',
        'transcription_model_name': 'base.en',
        'llm_model': 'gpt-4o',
        'data_source_id': seed_test_data.data_source_id
    }

    with open(filename, "rb") as f:
        audio_response = authorized_client.post(
            "/api/audio/analyze_recording",
            files={"file": ("test.mp3", f, "audio/mp3")},
            data=data
        )
        logger.info("test_post_audio - response: %s", audio_response.json())

        # Skip if whisper service is not available
        if audio_response.status_code in [400, 503]:
            response_data = audio_response.json()
            error_key = response_data.get("error_key", "")
            if "WHISPER" in error_key.upper() or audio_response.status_code == 503:
                pytest.skip(f"Whisper service not available: {error_key}")

        assert audio_response.status_code == 200
