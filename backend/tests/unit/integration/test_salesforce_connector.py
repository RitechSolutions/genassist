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


def _extract_soql(url: str) -> str:
    """Decode the SOQL query string from a /query/?q=<encoded> URL."""
    from urllib.parse import unquote

    marker = "/query/?q="
    assert marker in url
    return unquote(url.split(marker, 1)[1])


@pytest.mark.asyncio
async def test_fetch_knowledge_articles_builds_soql_and_normalizes():
    """FR-3/4/5: SOQL filters to Online articles and records are normalized."""
    connector = _connector()

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        return {
            "done": True,
            "records": [
                {
                    "Id": "kav-1",
                    "KnowledgeArticleId": "ka-1",
                    "ArticleNumber": "000001",
                    "Title": "How to reset",
                    "Summary": "A summary",
                    "Body__c": "<p>Body HTML</p>",
                    "LastPublishedDate": "2026-01-01T00:00:00.000+0000",
                }
            ],
        }

    with patch.object(
        connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request
    ) as mock_request:
        articles = await connector.fetch_knowledge_articles(content_field="Body__c")

    # The query call is the second call (after the token exchange).
    soql = _extract_soql(mock_request.await_args_list[1].args[1])
    assert "FROM Knowledge__kav" in soql
    assert "PublishStatus='Online'" in soql
    assert "Body__c" in soql
    assert "Language=" not in soql
    assert "WITH DATA CATEGORY" not in soql

    assert articles == [
        {
            "id": "ka-1",
            "title": "How to reset",
            "summary": "A summary",
            "body": "<p>Body HTML</p>",
            "updated_at": "2026-01-01T00:00:00.000+0000",
        }
    ]


@pytest.mark.asyncio
async def test_fetch_knowledge_articles_includes_language_filter():
    """FR-5: the Language predicate is added to the WHERE clause when provided."""
    connector = _connector()

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        return {"done": True, "records": []}

    with patch.object(
        connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request
    ) as mock_request:
        await connector.fetch_knowledge_articles(content_field="Body__c", language="en_US")

    soql = _extract_soql(mock_request.await_args_list[1].args[1])
    assert "PublishStatus='Online'" in soql
    assert "Language='en_US'" in soql


@pytest.mark.asyncio
async def test_fetch_knowledge_articles_data_category_after_where():
    """FR-5: WITH DATA CATEGORY appears AFTER the WHERE clause (distinct SOQL syntax)."""
    connector = _connector()

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        return {"done": True, "records": []}

    with patch.object(
        connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request
    ) as mock_request:
        await connector.fetch_knowledge_articles(
            content_field="Body__c",
            language="en_US",
            data_category="Geography__c ABOVE usa__c",
        )

    soql = _extract_soql(mock_request.await_args_list[1].args[1])
    assert "WITH DATA CATEGORY Geography__c ABOVE usa__c" in soql
    # data category clause must come after the WHERE clause
    assert soql.index("WHERE") < soql.index("WITH DATA CATEGORY")


@pytest.mark.asyncio
async def test_fetch_knowledge_articles_follows_next_records_url():
    """FR-3: pagination follows nextRecordsUrl until done == true."""
    connector = _connector()
    next_url = "/services/data/v60.0/query/01g000000000000AAA-2000"

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        if url.endswith(next_url):
            return {
                "done": True,
                "records": [{"KnowledgeArticleId": "ka-2", "Body__c": "b2"}],
            }
        # first page
        return {
            "done": False,
            "nextRecordsUrl": next_url,
            "records": [{"KnowledgeArticleId": "ka-1", "Body__c": "b1"}],
        }

    with patch.object(
        connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request
    ) as mock_request:
        articles = await connector.fetch_knowledge_articles(content_field="Body__c")

    ids = [a["id"] for a in articles]
    assert ids == ["ka-1", "ka-2"]
    # token + first page + next page = 3 requests, and the next page uses the token instance_url
    assert mock_request.await_count == 3
    assert mock_request.await_args_list[2].args[1] == (
        f"https://myorg.my.salesforce.com{next_url}"
    )


@pytest.mark.asyncio
async def test_fetch_knowledge_articles_rejects_invalid_content_field():
    """A missing/invalid content_field raises a clear error before any request."""
    connector = _connector()
    with pytest.raises(ValueError):
        await connector.fetch_knowledge_articles(content_field="")
    with pytest.raises(ValueError):
        await connector.fetch_knowledge_articles(content_field="Body__c; DROP")


@pytest.mark.asyncio
async def test_fetch_knowledge_articles_rejects_injected_data_category():
    """FR-5/security: a data_category that isn't a well-formed WITH DATA CATEGORY filter
    (contains quotes/keywords for injection, or lacks a category selector) is rejected."""
    connector = _connector()
    # Injection attempt via a string literal / extra clause.
    with pytest.raises(ValueError):
        await connector.fetch_knowledge_articles(
            content_field="Body__c", data_category="Geo__c AT usa__c' OR '1'='1"
        )
    # Missing the AT/ABOVE/BELOW/ABOVE_OR_BELOW selector.
    with pytest.raises(ValueError):
        await connector.fetch_knowledge_articles(
            content_field="Body__c", data_category="LIMIT 1"
        )


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
