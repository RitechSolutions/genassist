from datetime import datetime
import pytest
from app.db.seed.seed_data_config import seed_test_data
import logging


logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def new_in_progress_conversation_data():
    return {
        "messages": [],
        "operator_id": seed_test_data.operator_id,
        "data_source_id": seed_test_data.data_source_id,
        "customer_id": None,
        "recorded_at": "2025-10-03T10:00:00Z",
    }


def _ensure_active_agent(client):
    """Ensure at least one agent is active for tests that require an active agent."""
    agents_resp = client.get("/api/genagent/agents/configs/")
    assert agents_resp.status_code == 200
    agents = agents_resp.json()

    for agent in agents:
        if agent.get("is_active") == 0:
            agent_id = agent["id"]
            switch_response = client.post(f"/api/genagent/agents/switch/{agent_id}")
            if switch_response.status_code != 200:
                logger.info(
                    f"Error response in switch agent {agent_id}: {switch_response.json()}"
                )
            assert switch_response.status_code == 200


@pytest.mark.asyncio(loop_scope="function")
async def test_create_in_progress_conversation(
    authorized_client, authorized_client_agent, new_in_progress_conversation_data
):
    _ensure_active_agent(authorized_client)

    response = authorized_client_agent.post(
        "/api/conversations/in-progress/start", json=new_in_progress_conversation_data
    )
    assert response.status_code == 200

    logger.info("test_create_in_progress_conversation - response: %s", response.json())

    new_in_progress_conversation_data["id"] = response.json()["conversation_id"]


@pytest.mark.asyncio(loop_scope="function")
async def test_update_in_progress_conversation(
    authorized_client, authorized_client_agent, new_in_progress_conversation_data
):
    _ensure_active_agent(authorized_client)
    payload = {
        "messages": [
            {
                "create_time": datetime.now().isoformat(),
                "start_time": 2.0,
                "end_time": 4.0,
                "speaker": "customer",
                "text": "Thank you I dont need anything.",
                "type": "message",
            },
        ],
        "metadata": {
            "thread_id": new_in_progress_conversation_data["id"],
        },
    }

    response = authorized_client_agent.patch(
        f"/api/conversations/in-progress/update/{new_in_progress_conversation_data['id']}",
        json=payload,
    )

    data = response.json()
    logger.info("test_update_in_progress_conversation - response: %s", response.json())

    # If the pipeline flips the agent state between tests, recover and retry once
    if (
        response.status_code == 400
        and isinstance(data, dict)
        and data.get("error_key") == "AGENT_INACTIVE"
    ):
        _ensure_active_agent(authorized_client)
        response = authorized_client_agent.patch(
            f"/api/conversations/in-progress/update/{new_in_progress_conversation_data['id']}",
            json=payload,
        )
        data = response.json()
        logger.info(
            "test_update_in_progress_conversation - retried response: %s",
            response.json(),
        )

    assert response.status_code == 200

    assert "id" in data
    assert data["id"] == new_in_progress_conversation_data["id"]


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("token", ["supervisor"], indirect=True)
async def test_supervisor_takeover_conversation(
    authorized_client, new_in_progress_conversation_data
):
    response = authorized_client.patch(
        f"/api/conversations/in-progress/takeover-super/{new_in_progress_conversation_data['id']}"
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["status"] == "takeover"
    logger.info("test_supervisor_takeover_conversation - response: %s", response.json())


@pytest.mark.asyncio(loop_scope="function")
async def test_finalize_in_progress_conversation(
    authorized_client, new_in_progress_conversation_data
):
    payload = {
        "llm_analyst_id": seed_test_data.llm_analyst_kpi_analyzer_id,
        "type": "finalize",
    }

    response = authorized_client.patch(
        f"/api/conversations/in-progress/finalize/{new_in_progress_conversation_data['id']}",
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data or "analysis_id" in data
    logger.info(
        "test_finalize_in_progress_conversation - response: %s", response.json()
    )


@pytest.mark.asyncio(loop_scope="function")
async def test_update_after_finalize(
    authorized_client, new_in_progress_conversation_data
):
    # Finalize first
    payload = {"llm_analyst_id": seed_test_data.llm_analyst_speaker_separator_id}
    finalize_resp = authorized_client.patch(
        f"/api/conversations/in-progress/finalize/{new_in_progress_conversation_data['id']}",
        json=payload,
    )
    assert finalize_resp.status_code == 400
    logger.info(
        "test_update_after_finalize try finalize again - response: %s",
        finalize_resp.json(),
    )

    # Try updating again
    update_payload = {
        "messages": [
            {
                "start_time": 5.0,
                "end_time": 7.0,
                "speaker": "customer",
                "text": "More details after closing the case.",
            }
        ],
        "type": "message",
        "metadata": {
            "thread_id": new_in_progress_conversation_data["id"],
        },
    }

    response = authorized_client.patch(
        f"/api/conversations/in-progress/update/{new_in_progress_conversation_data['id']}",
        json=update_payload,
    )
    assert response.status_code == 400
    logger.info("test_update_after_finalize - response: %s", response.json())


@pytest.mark.asyncio(loop_scope="function")
async def test_filter_conversations_count(authorized_client):
    params = [
        ("conversation_status", "finalized"),
        ("conversation_status", "in_progress"),
    ]
    response = authorized_client.get("/api/conversations/filter/count", params=params)

    logger.info("test_filter_conversations_count - response: %s", response.json())

    assert response.status_code == 200

    data = response.json()
    # Ensure the response contains a numeric count >= 0
    assert isinstance(data, (int, float)), f"Expected numeric count, got {type(data)}"
    assert data >= 0
