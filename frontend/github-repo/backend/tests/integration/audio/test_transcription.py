import os
import pytest
import logging
from app.db.seed.seed_data_config import seed_test_data



logger = logging.getLogger(__name__)

#@pytest.mark.skip(reason="Does not work")
@pytest.mark.asyncio
async def test_post_audio(client):
    op_response = client.get("/api/operators/", headers={"X-API-Key": "test123"})
    logger.info("test_post_audio - operators: %s", op_response.json())
    op_id = op_response.json()[0]["id"]
    
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = dir_path+'/tech-support.mp3'
    logger.info("uploading test file:"+filename)
    
    data = {'operator_id': op_id, 'recorded_at':'2025-04-01T14:25:00Z',
            'transcription_model_name':'base.en', 'llm_model':'gpt-4o',
            'data_source_id': seed_test_data.data_source_id}
    
    with open(filename, "rb") as f:
        audio_response = client.post("/api/audio/analyze_recording",
                                    files={"file": ("test.mp3", f, "audio/mp3")},
                                    data=data,
                                    headers={"X-API-Key": "test123"})
        logger.info("test_post_audio - response: %s", audio_response.json())
        assert audio_response.status_code == 200
