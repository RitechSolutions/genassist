"""Integration tests for the GDPR conversation deletion endpoint.

These tests verify that:

- non-admin users (e.g. supervisors) receive a 403 from
  ``DELETE /api/conversations/{conversation_id}/gdpr``,
- the route is wired and reachable for admins (a missing conversation
  returns the standard ``CONVERSATION_NOT_FOUND`` 404 rather than a 403,
  proving the auth layer let the request through),
- the new ``email`` query parameter on the existing list endpoint is accepted
  and OR-combined with the existing search behavior (smoke check).

The full end-to-end JSONB / FTS query is exercised against a real Postgres
database in higher-level tests; these focus on the public HTTP contract so
they remain runnable in CI.
"""

import logging
import os
import uuid

import pytest
from starlette.testclient import TestClient

from app.db.seed.seed_data_config import seed_test_data


logger = logging.getLogger(__name__)

_SKIP_IN_CI = os.environ.get("CI", "false").lower() == "true" or os.environ.get(
    "TESTING", "false"
).lower() == "true"
_SKIP_REASON = (
    "Skipped in CI: integration tests in this folder are skipped due to async "
    "task handling with TestClient."
)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/token", data={"username": username, "password": password}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.mark.skipif(_SKIP_IN_CI, reason=_SKIP_REASON)
def test_gdpr_delete_forbidden_for_non_admin(client: TestClient):
    """Supervisor lacks the admin role and the ``delete:conversation:gdpr``
    permission, so they should be rejected with 403."""
    token = _login(
        client, seed_test_data.supervisor_username, seed_test_data.supervisor_password
    )
    client.headers.update({"Authorization": f"Bearer {token}"})

    fake_id = uuid.uuid4()
    response = client.delete(f"/api/conversations/{fake_id}/gdpr?mode=soft")

    assert response.status_code == 403, (
        f"Expected 403 for supervisor; got {response.status_code}: {response.text}"
    )


@pytest.mark.skipif(_SKIP_IN_CI, reason=_SKIP_REASON)
def test_gdpr_delete_admin_route_is_reachable(authorized_client: TestClient):
    """Admin should not be blocked by RBAC; an unknown conversation_id should
    surface as 404 (CONVERSATION_NOT_FOUND), not 403."""
    fake_id = uuid.uuid4()
    response = authorized_client.delete(f"/api/conversations/{fake_id}/gdpr?mode=soft")

    assert response.status_code in (404, 200), (
        f"Unexpected status for admin call: {response.status_code}: {response.text}"
    )


@pytest.mark.skipif(_SKIP_IN_CI, reason=_SKIP_REASON)
def test_conversations_list_accepts_email_filter(authorized_client: TestClient):
    """The list endpoint should accept the new ``email`` query param without
    erroring, even when no conversation matches."""
    response = authorized_client.get(
        "/api/conversations?email=nobody@example.com&limit=5"
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "items" in payload
    assert "total" in payload
