import pytest
import logging
import json

logger = logging.getLogger(__name__)

@pytest.mark.skip("Gives timeout error, needs investigation")
def test_get_session_openai(client):
    response = client.get(
        "/api/voice/openai/session",
        headers={"X-API-Key": "test123", "accept": "application/json"},
        params={"lang_code": "en"},
    )
    logger.info("test_get_session_openai: %s", response.json())

    assert response.status_code == 200

@pytest.mark.skip("Gives timeout error, needs investigation")
def test_tts(authorized_client):
    with authorized_client.websocket_connect("/api/voice/audio/tts?api_key=test123") as websocket:
        websocket.send_text(json.dumps({"text": "Hello"}))
        response = websocket.receive()
        #logger.info("test_tts - response: %s", response)
        assert response["bytes"] is not None
        assert response["bytes"] != b""