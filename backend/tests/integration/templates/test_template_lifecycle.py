"""One template through its life: save, publish, reject with a reason, publish again, approve, delete."""
import pytest

FLAG = "feature.templateMarketplace"
TEMPLATES = "/api/genagent/templates"
REASON = "Add a clearer description"


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


@pytest.fixture
def marketplace_on(admin_client):
    flag = next(f for f in admin_client.get("/api/feature-flags/").json() if f["key"] == FLAG)
    original = {"val": flag["val"], "is_active": flag["is_active"]}
    admin_client.patch(f"/api/feature-flags/{flag['id']}", json={"val": "true", "is_active": 1})
    yield
    admin_client.patch(f"/api/feature-flags/{flag['id']}", json=original)


@pytest.fixture
def own_agent(admin_client):
    agent = admin_client.post(
        "/api/genagent/agents/configs",
        json={
            "name": "Lifecycle agent",
            "description": "Agent saved as a template",
            "welcome_message": "Hello",
            "possible_queries": ["What can you do?"],
        },
    ).json()
    yield agent
    admin_client.delete(f"/api/genagent/agents/configs/{agent['id']}")


@pytest.fixture
def cleanup(admin_client):
    # Deletes the test's template even when an assertion stops the test early.
    template_ids = []
    yield template_ids
    for template_id in template_ids:
        admin_client.delete(f"{TEMPLATES}/{template_id}")


def _own_card(client, template_id):
    return next(item for item in client.get(TEMPLATES).json() if item["id"] == template_id)


def test_a_template_from_save_to_delete(admin_client, marketplace_on, own_agent, cleanup):
    saved = admin_client.post(f"{TEMPLATES}/from-agent", json={"agent_id": own_agent["id"], "title": "Lifecycle"})
    assert saved.status_code == 201, saved.text
    template_id = saved.json()["id"]
    cleanup.append(template_id)

    # Publish, then the reviewer rejects with a reason that only the author sees.
    first_copy = admin_client.post(f"{TEMPLATES}/{template_id}/publish").json()["id"]
    rejected = admin_client.post(f"{TEMPLATES}/review/{first_copy}/reject", json={"reason": REASON})
    assert rejected.status_code == 204, rejected.text
    card = _own_card(admin_client, template_id)
    assert (card["publish_status"], card["rejection_reason"]) == ("rejected", REASON)

    # Publishing again means a new review, and the old reason is gone.
    second_copy = admin_client.post(f"{TEMPLATES}/{template_id}/publish").json()["id"]
    card = _own_card(admin_client, template_id)
    assert (card["publish_status"], card["rejection_reason"]) == ("pending", None)
    queued = next(item for item in admin_client.get(f"{TEMPLATES}/review").json() if item["id"] == second_copy)
    assert queued["rejection_reason"] is None

    approved = admin_client.post(f"{TEMPLATES}/review/{second_copy}/approve")
    assert approved.status_code == 204, approved.text
    assert _own_card(admin_client, template_id)["publish_status"] == "approved"
    shared = admin_client.get(f"{TEMPLATES}/{second_copy}")
    assert shared.status_code == 200 and shared.json()["is_global"]
    assert "rejection_reason" not in shared.json()

    # Deleting the template removes the shared copy for every tenant in the same call.
    deleted = admin_client.delete(f"{TEMPLATES}/{template_id}")
    assert deleted.status_code == 204, deleted.text
    assert admin_client.get(f"{TEMPLATES}/{second_copy}").status_code == 404
    assert all(item["id"] not in (template_id, second_copy) for item in admin_client.get(TEMPLATES).json())
    assert admin_client.post(f"{TEMPLATES}/{template_id}/unpublish").status_code == 404
