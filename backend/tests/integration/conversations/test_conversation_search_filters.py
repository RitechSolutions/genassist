"""Integration tests: conversation search combined with filters that join the analysis table"""

import pytest

SENTIMENT_PARAMS = {
    "sentiment": "negative",
    "hostility_positive_max": 3,
    "hostility_neutral_max": 6,
}

SEARCH_WITH_ANALYSIS_FILTERS = [
    pytest.param(SENTIMENT_PARAMS, id="sentiment"),
    pytest.param({"customer_satisfaction_min": 7}, id="score-min"),
    pytest.param({"quality_of_service_min": 2, "quality_of_service_max": 8}, id="score-range"),
    pytest.param({"order_by": "customer_satisfaction"}, id="order-by-score"),
]


@pytest.mark.parametrize("analysis_params", SEARCH_WITH_ANALYSIS_FILTERS)
def test_list_conversations_with_search_and_analysis_filter(authorized_client, analysis_params):
    params = {"search": "refund", **analysis_params}

    response = authorized_client.get("/api/conversations", params=params)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["total"] >= len(body["items"])


@pytest.mark.parametrize("analysis_params", SEARCH_WITH_ANALYSIS_FILTERS)
def test_count_conversations_with_search_and_analysis_filter(authorized_client, analysis_params):
    params = {"search": "refund", **analysis_params}

    response = authorized_client.get("/api/conversations/filter/count", params=params)

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), int)
