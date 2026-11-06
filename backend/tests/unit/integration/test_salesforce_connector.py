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


def _salesforce_length(text):
    return len(text.encode("utf-16-le")) // 2


@pytest.mark.parametrize(
    "text, max_length, expected",
    [
        ("short", 10, "short"),
        ("abcdefghij", 10, "abcdefghij"),
        ("abcdefghijk", 10, "abcdefg..."),
        ("😀😀😀😀😀😀", 10, "😀😀😀..."),
        ("ab😀😀😀😀", 6, "ab..."),
    ],
)
def test_fit_to_length_counts_like_salesforce_and_never_splits_emoji(text, max_length, expected):
    from app.modules.integration.salesforce import _fit_to_length

    fitted = _fit_to_length(text, max_length, "...")
    assert fitted == expected
    assert _salesforce_length(fitted) <= max_length


@pytest.mark.asyncio
async def test_create_case_fits_subject_and_description_and_contact_fields_win():
    connector = _connector()

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        return {"id": "500AB", "success": True}

    long_chat = "Customer: my card failed 😀 " * 2000
    with patch.object(connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request) as mock_request:
        await connector.create_case(
            subject="S" * 300,
            description=long_chat,
            custom_fields=[{"key": "SuppliedEmail", "value": "old@example.com"}, {"key": "Origin", "value": "Chatbot"}],
            contact_fields={"SuppliedEmail": "alice@example.com", "SuppliedName": "Alice"},
        )

    body = mock_request.await_args_list[1].kwargs["json"]
    assert _salesforce_length(body["Subject"]) <= 255
    assert body["Subject"].endswith("...")
    assert _salesforce_length(body["Description"]) <= 32000
    assert body["Description"].endswith("\n\n[truncated]")
    assert body["Description"].startswith("Customer: my card failed")
    assert body["SuppliedEmail"] == "alice@example.com"
    assert body["SuppliedName"] == "Alice"
    assert body["Origin"] == "Chatbot"


@pytest.mark.asyncio
async def test_rejected_request_logs_and_returns_only_error_code_and_field():
    import httpx

    customer_text = "my card 4111 failed, email jane@example.com"
    url = "https://myorg.my.salesforce.com/services/data/v60.0/sobjects/Case"
    reply = httpx.Response(
        400,
        json=[{"message": f"Description: data value too large: {customer_text}", "errorCode": "STRING_TOO_LONG", "fields": ["Description"]}],
        request=httpx.Request("POST", url),
    )
    connector = _connector()

    with patch.object(httpx.AsyncClient, "request", new=AsyncMock(return_value=reply)), patch(
        "app.modules.integration.salesforce.logger"
    ) as logger:
        with pytest.raises(HTTPException) as raised:
            await connector._make_request("POST", url, json={})

    assert raised.value.detail == "STRING_TOO_LONG on Description"
    logged = " ".join(str(arg) for call in logger.error.call_args_list for arg in call.args)
    assert "STRING_TOO_LONG on Description" in logged
    assert customer_text not in logged


@pytest.mark.parametrize(
    "status, body, expected",
    [
        (400, [{"message": "Email: invalid email address: guest", "errorCode": "INVALID_EMAIL_ADDRESS", "fields": ["SuppliedEmail"]}], "INVALID_EMAIL_ADDRESS on SuppliedEmail"),
        (400, [{"message": "duplicate value found: Name duplicates value on record", "errorCode": "DUPLICATE_VALUE", "fields": []}], "DUPLICATE_VALUE"),
        (400, [{"message": "a", "errorCode": "A", "fields": ["X"]}, {"message": "b", "errorCode": "B", "fields": ["Y", "Z"]}], "A on X; B on Y, Z"),
        (400, {"error": "invalid_client", "error_description": "invalid client credentials"}, "invalid_client: invalid client credentials"),
        (401, {"error": "invalid_grant"}, "invalid_grant"),
        (500, None, "HTTP 500"),
    ],
)
def test_safe_error_detail(status, body, expected):
    import httpx

    from app.modules.integration.salesforce import _safe_error_detail

    response = httpx.Response(status, json=body) if body is not None else httpx.Response(status, text="<html>oops</html>")
    assert _safe_error_detail(response) == expected


def test_custom_subject_and_description_are_cut_too():
    from app.modules.integration.salesforce import build_case_payload

    payload = build_case_payload(
        "Help", "short", [{"key": "Description", "value": "x" * 40000}, {"key": "Subject", "value": "S" * 300}], None
    )
    assert _salesforce_length(payload["Description"]) == 32000
    assert _salesforce_length(payload["Subject"]) == 255


@pytest.mark.asyncio
async def test_failed_read_keeps_salesforce_message():
    import httpx

    url = "https://myorg.my.salesforce.com/services/data/v60.0/query/?q=SELECT"
    reply = httpx.Response(
        400,
        json=[{"message": "No such column 'Body__c' on entity 'Knowledge__kav'", "errorCode": "INVALID_FIELD"}],
        request=httpx.Request("GET", url),
    )
    with patch.object(httpx.AsyncClient, "request", new=AsyncMock(return_value=reply)):
        with pytest.raises(HTTPException) as raised:
            await _connector()._make_request("GET", url)

    assert "No such column 'Body__c'" in raised.value.detail


@pytest.mark.parametrize(
    "contact_fields, expected",
    [
        ({"SuppliedEmail": "null", "SuppliedName": "None", "SuppliedPhone": "undefined"}, {}),
        ({"SuppliedEmail": "guest"}, {}),
        ({"SuppliedEmail": "n/a"}, {}),
        ({"SuppliedEmail": "alice%40example.com"}, {}),
        ({"SuppliedEmail": "jürgen@例え.jp"}, {}),
        ({"SuppliedEmail": "a.b+tag@sub.example.co.uk"}, {"SuppliedEmail": "a.b+tag@sub.example.co.uk"}),
        ({"SuppliedEmail": "a" * 69 + "@example.com"}, {}),
        ({"SuppliedEmail": " alice@example.com "}, {"SuppliedEmail": "alice@example.com"}),
        ({"SuppliedEmail": "Jane <jane@acme.com>"}, {"SuppliedEmail": "jane@acme.com"}),
        ({"SuppliedEmail": '"Jane" <jane@acme.com>'}, {"SuppliedEmail": "jane@acme.com"}),
        ({"SuppliedEmail": "<jane@acme.com>"}, {"SuppliedEmail": "jane@acme.com"}),
        ({"SuppliedEmail": "Jürgen <j@example.com>"}, {"SuppliedEmail": "j@example.com"}),
        ({"SuppliedEmail": "Dr. Jane Doe <jane@acme.com>"}, {"SuppliedEmail": "jane@acme.com"}),
        ({"SuppliedEmail": "Jane Doe (Acme) <jane@acme.com>"}, {"SuppliedEmail": "jane@acme.com"}),
        ({"SuppliedEmail": "jane@xn--mnchen-3ya.de"}, {"SuppliedEmail": "jane@xn--mnchen-3ya.de"}),
        ({"SuppliedEmail": "jane@münchen.de"}, {"SuppliedEmail": "jane@xn--mnchen-3ya.de"}),
        ({"SuppliedEmail": "jane@acme.com, bob@acme.com"}, {}),
        ({"SuppliedEmail": "jane@corp.local"}, {}),
        ({"SuppliedEmail": "qa@example.test"}, {}),
        ({"SuppliedName": "N" * 100}, {"SuppliedName": "N" * 80}),
        ({"SuppliedPhone": "+1 555 0100 ext 22, call after 5pm 📞 mobile"}, {"SuppliedPhone": "+1 555 0100 ext 22, call after 5pm 📞 mo"}),
        ({"SuppliedName": None, "SuppliedPhone": ""}, {}),
    ],
)
def test_contact_fields_are_cleaned_before_sending(contact_fields, expected):
    from app.modules.integration.salesforce import clean_contact_fields

    assert clean_contact_fields(contact_fields) == expected


@pytest.mark.asyncio
async def test_case_with_unusable_contact_boxes_is_still_sent():
    connector = _connector()

    async def _fake_request(method, url, json=None, data=None, headers=None, timeout=10.0):
        if url.endswith("/services/oauth2/token"):
            return _TOKEN_RESPONSE
        return {"id": "500AB", "success": True}

    with patch.object(connector, "_make_request", new_callable=AsyncMock, side_effect=_fake_request) as mock_request:
        result = await connector.create_case(
            subject="Refund",
            description="Customer asked about a refund",
            contact_fields={"SuppliedEmail": "guest", "SuppliedName": "null", "SuppliedPhone": "5" * 60},
        )

    body = mock_request.await_args_list[1].kwargs["json"]
    assert result["status"] == 200
    assert "SuppliedEmail" not in body
    assert "SuppliedName" not in body
    assert body["SuppliedPhone"] == "5" * 40


@pytest.mark.asyncio
async def test_network_error_log_has_no_request_details():
    import httpx

    url = "https://myorg.my.salesforce.com/services/data/v60.0/sobjects/Case"
    connector = _connector()

    with patch.object(httpx.AsyncClient, "request", new=AsyncMock(side_effect=httpx.ReadTimeout("timed out"))), patch(
        "app.modules.integration.salesforce.logger"
    ) as logger:
        with pytest.raises(HTTPException) as raised:
            await connector._make_request("POST", url, json={"Description": "Customer Jane Doe says: card charged twice"})

    assert raised.value.status_code == 500
    call = logger.error.call_args
    assert "exc_info" not in call.kwargs
    logged = " ".join(str(arg) for arg in call.args)
    assert "ReadTimeout" in logged
    assert "Jane Doe" not in logged


@pytest.mark.parametrize(
    "custom_fields, contact_fields, expected",
    [
        ([{"key": "SuppliedEmail", "value": "null"}, {"key": "SuppliedName", "value": "N" * 200}], None, {"SuppliedName": "N" * 80}),
        ([{"key": "SuppliedEmail", "value": "Jane <jane@acme.com>"}], None, {"SuppliedEmail": "jane@acme.com"}),
        ([{"key": "SuppliedEmail", "value": "custom@example.com"}], {"SuppliedEmail": "guest"}, {"SuppliedEmail": "custom@example.com"}),
        ([{"key": "SuppliedEmail", "value": "bad"}], {"SuppliedEmail": "also bad"}, {}),
        ([{"key": "SuppliedEmail", "value": "custom@example.com"}], {"SuppliedEmail": "box@example.com"}, {"SuppliedEmail": "box@example.com"}),
        ([{"key": "SuppliedPhone", "value": "5" * 60}], {"SuppliedPhone": "null"}, {"SuppliedPhone": "5" * 40}),
        ([{"key": "suppliedemail", "value": "guest"}], {"SuppliedEmail": "Jane <jane@acme.com>"}, {"SuppliedEmail": "jane@acme.com"}),
        ([{"key": " SUPPLIEDNAME ", "value": "N" * 120}], None, {"SuppliedName": "N" * 80}),
        ([{"key": "suppliedEmail", "value": "custom@example.com"}], {"SuppliedEmail": "null"}, {"SuppliedEmail": "custom@example.com"}),
    ],
)
def test_contact_fields_from_custom_fields_are_cleaned_and_a_usable_box_wins(custom_fields, contact_fields, expected):
    from app.modules.integration.salesforce import build_case_payload

    payload = build_case_payload("Subject", "Description", custom_fields, contact_fields)

    assert {k: v for k, v in payload.items() if k.startswith("Supplied")} == expected


@pytest.mark.parametrize("key", ["description", " DESCRIPTION ", "Description"])
def test_description_custom_field_in_any_case_is_cut_to_length(key):
    from app.modules.integration.salesforce import _salesforce_length, build_case_payload

    payload = build_case_payload("Subject", "Short", [{"key": key, "value": "x" * 40000}])

    assert [k for k in payload if k.strip().lower() == "description"] == ["Description"]
    assert _salesforce_length(payload["Description"]) == 32000


def test_subject_custom_field_in_any_case_is_cut_to_length():
    from app.modules.integration.salesforce import build_case_payload

    payload = build_case_payload("Short", "Description", [{"key": "subject", "value": "s" * 300}])

    assert [k for k in payload if k.lower() == "subject"] == ["Subject"]
    assert len(payload["Subject"]) == 255
