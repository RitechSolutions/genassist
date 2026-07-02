"""Unit tests for SalesforceConnector (httpx transport mocked).

Covers the OAuth2 client-credentials token request shape, that ``create_case`` POSTs
to the Case sobject path using the token-returned ``instance_url``, and that
``test_connection`` returns success / raises (FR-4, FR-5, FR-11).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.modules.integration.salesforce import (
    SALESFORCE_API_VERSION,
    SalesforceConnector,
)

_CREDS = {
    "instance_url": "https://login.salesforce.com",
    "client_id": "client-id",
    "client_secret": "client-secret",
}

_TOKEN_RESPONSE = {
    "access_token": "ACCESS_TOKEN",
    "instance_url": "https://myorg.my.salesforce.com",
}


def _connector():
    return SalesforceConnector(**_CREDS)


@pytest.mark.asyncio
async def test_get_access_token_builds_client_credentials_body():
    """FR-11: token request posts a client-credentials grant (client id + secret only)."""
    connector = _connector()
    with patch.object(
        connector, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = _TOKEN_RESPONSE
        token = await connector._get_access_token()

    assert token == "ACCESS_TOKEN"
    method, url = mock_request.await_args.args[:2]
    assert method == "POST"
    assert url == "https://login.salesforce.com/services/oauth2/token"
    form = mock_request.await_args.kwargs["data"]
    assert form["grant_type"] == "client_credentials"
    assert form["client_id"] == "client-id"
    assert form["client_secret"] == "client-secret"
    # no user credentials in the client-credentials flow
    assert "username" not in form
    assert "password" not in form
    # the connector records the instance_url returned by SalesForce
    assert connector._token_instance_url == "https://myorg.my.salesforce.com"


@pytest.mark.asyncio
async def test_create_case_posts_to_case_path_with_token_instance_url():
    """FR-4/FR-5: create_case POSTs to the Case sobject path on the token instance_url."""
    connector = _connector()
    case_result = {"id": "500AB", "success": True}

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        return case_result

    with patch.object(
        connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request
    ) as mock_request:
        result = await connector.create_case(
            subject="Help",
            description="It broke",
            custom_fields=[
                {"key": "Priority", "value": "High"},
                {"key": "SuppliedName", "value": "Jane"},
            ],
        )

    assert result == {"status": 200, "data": case_result}

    # The second call is the Case create.
    create_call = mock_request.await_args_list[1]
    method, url = create_call.args[:2]
    assert method == "POST"
    assert url == (
        f"https://myorg.my.salesforce.com/services/data/{SALESFORCE_API_VERSION}/sobjects/Case"
    )
    body = create_call.kwargs["json"]
    assert body["Subject"] == "Help"
    assert body["Description"] == "It broke"
    # custom fields mapped by API name
    assert body["Priority"] == "High"
    assert body["SuppliedName"] == "Jane"
    headers = create_call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer ACCESS_TOKEN"


@pytest.mark.asyncio
async def test_create_case_assigns_labels_as_topics():
    """Labels are assigned as Topics: find-or-create the Topic, then TopicAssignment."""
    connector = _connector()

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        if url.endswith("/sobjects/Case"):
            return {"id": "500CASE", "success": True}
        if "/query/" in url:
            # "billing" already exists; "urgent" does not.
            if "billing" in url:
                return {"records": [{"Id": "TOPIC_BILLING"}]}
            return {"records": []}
        if url.endswith("/sobjects/Topic"):
            return {"id": "TOPIC_URGENT", "success": True}
        if url.endswith("/sobjects/TopicAssignment"):
            return {"id": "TA", "success": True}
        return {}

    with patch.object(
        connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request
    ) as mock_request:
        result = await connector.create_case(
            subject="Help", description="broke", labels=["billing", "urgent"]
        )

    assert result == {"status": 200, "data": {"id": "500CASE", "success": True}}

    assignments = [
        c.kwargs["json"]
        for c in mock_request.await_args_list
        if c.args[1].endswith("/sobjects/TopicAssignment")
    ]
    # One TopicAssignment per label, both linked to the created Case.
    assert {"EntityId": "500CASE", "TopicId": "TOPIC_BILLING"} in assignments
    assert {"EntityId": "500CASE", "TopicId": "TOPIC_URGENT"} in assignments


@pytest.mark.asyncio
async def test_topic_create_duplicate_race_refetches_existing():
    """A DUPLICATE_VALUE on Topic create is recovered by re-querying (label not lost)."""
    connector = _connector()
    calls = {"query": 0}

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        if url.endswith("/sobjects/Case"):
            return {"id": "500CASE"}
        if "/query/" in url:
            calls["query"] += 1
            # First lookup: not found → triggers create. Second (post-collision): found.
            return {"records": [{"Id": "TOPIC_X"}]} if calls["query"] > 1 else {"records": []}
        if url.endswith("/sobjects/Topic"):
            raise HTTPException(status_code=400, detail="DUPLICATE_VALUE: duplicate")
        if url.endswith("/sobjects/TopicAssignment"):
            return {"id": "TA"}
        return {}

    with patch.object(
        connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request
    ) as mock_request:
        await connector.create_case(subject="s", description="d", labels=["x"])

    assignments = [
        c.kwargs["json"]
        for c in mock_request.await_args_list
        if c.args[1].endswith("/sobjects/TopicAssignment")
    ]
    assert {"EntityId": "500CASE", "TopicId": "TOPIC_X"} in assignments


@pytest.mark.asyncio
async def test_label_assignment_failure_does_not_fail_case():
    """A Topic-assignment failure is swallowed — the created Case is still returned."""
    connector = _connector()

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        if url.endswith("/sobjects/Case"):
            return {"id": "500CASE"}
        # Topics disabled / no access -> query fails.
        raise HTTPException(status_code=400, detail="Topics not enabled")

    with patch.object(
        connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request
    ):
        result = await connector.create_case(
            subject="Help", description="broke", labels=["x"]
        )

    assert result == {"status": 200, "data": {"id": "500CASE"}}


@pytest.mark.asyncio
async def test_create_case_returns_error_envelope_with_real_status_and_detail():
    """create_case surfaces the real SalesForce status + detail (not an opaque 500)."""
    connector = _connector()
    with patch.object(
        connector, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = HTTPException(
            status_code=400, detail='{"error":"invalid_client"}'
        )
        result = await connector.create_case(subject="s", description="d")

    assert result == {"status": 400, "data": {"error": '{"error":"invalid_client"}'}}


@pytest.mark.asyncio
async def test_test_connection_success():
    """FR-11: test_connection performs the token exchange and reports success."""
    with patch.object(
        SalesforceConnector, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = _TOKEN_RESPONSE
        result = await SalesforceConnector.test_connection(
            {
                "salesforce_instance_url": "https://login.salesforce.com",
                "salesforce_client_id": "client-id",
                "salesforce_client_secret": "client-secret",
            }
        )

    assert result == {
        "success": True,
        "message": "Successfully connected to SalesForce.",
    }


@pytest.mark.asyncio
async def test_test_connection_raises_on_auth_failure():
    """FR-11: an authentication failure propagates (caught by datasources dispatch)."""
    with patch.object(
        SalesforceConnector, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = HTTPException(status_code=401, detail="invalid")
        with pytest.raises(HTTPException):
            await SalesforceConnector.test_connection(
                {
                    "salesforce_instance_url": "https://login.salesforce.com",
                    "salesforce_client_id": "client-id",
                    "salesforce_client_secret": "client-secret",
                }
            )
