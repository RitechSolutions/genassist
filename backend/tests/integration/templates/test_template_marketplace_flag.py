"""Template routes answer only while the tenant has the marketplace flag turned on."""
from uuid import uuid4

import pytest

FLAG = "feature.templateMarketplace"
TEMPLATES = "/api/genagent/templates"


@pytest.fixture
def admin_client(client, token):
    # The session client is shared with the API-key fixture, so set the admin session for these calls.
    saved = {name: client.headers.get(name) for name in ("Authorization", "X-API-Key")}
    client.headers.pop("X-API-Key", None)
    client.headers["Authorization"] = f"Bearer {token}"
    yield client
    for name, value in saved.items():
        if value is None:
            client.headers.pop(name, None)
        else:
            client.headers[name] = value


def _flag(client):
    return next(flag for flag in client.get("/api/feature-flags/").json() if flag["key"] == FLAG)


@pytest.fixture
def set_flag(admin_client):
    flag = _flag(admin_client)
    original = {"val": flag["val"], "is_active": flag["is_active"]}

    def update(**changes):
        response = admin_client.patch(f"/api/feature-flags/{flag['id']}", json=changes)
        assert response.status_code == 200, response.text

    yield update
    update(**original)


def test_a_new_database_has_the_flag_turned_off(admin_client):
    flag = _flag(admin_client)
    assert (flag["val"], flag["is_active"]) == ("false", 1)


@pytest.mark.parametrize("val, is_active", [("false", 1), ("true", 0)])
def test_template_calls_answer_403_while_the_flag_is_off(admin_client, set_flag, val, is_active):
    set_flag(val=val, is_active=is_active)
    missing = uuid4()
    calls = [
        ("GET", TEMPLATES, None),
        ("GET", f"{TEMPLATES}/{missing}", None),
        ("POST", f"{TEMPLATES}/{missing}/install", {}),
        ("POST", f"{TEMPLATES}/{missing}/publish", None),
        ("POST", f"{TEMPLATES}/from-agent", {"agent_id": str(uuid4()), "title": "Support"}),
        ("DELETE", f"{TEMPLATES}/{missing}", None),
    ]
    for method, path, body in calls:
        response = admin_client.request(method, path, json=body)
        assert response.status_code == 403, (method, path, response.text)
        assert response.json()["error_key"] == "TEMPLATE_MARKETPLACE_DISABLED"


def test_template_calls_answer_while_the_flag_is_on(admin_client, set_flag):
    set_flag(val="true", is_active=1)
    assert admin_client.get(TEMPLATES).status_code == 200
    assert admin_client.get(f"{TEMPLATES}/{uuid4()}").status_code == 404


def test_sign_in_is_checked_before_the_flag(admin_client, set_flag):
    set_flag(val="false", is_active=1)
    response = admin_client.get(TEMPLATES, headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_agent_list_items_say_whether_the_user_created_them(admin_client):
    items = admin_client.get("/api/genagent/agents/configs/list").json()["items"]
    assert items
    assert all(isinstance(item["is_mine"], bool) and "created_by" not in item for item in items)
