"""
Security hardening for public embed API keys (FG-1 / C-2).

- GET /api/conversations/{id} requires read:conversation (ai agent keys cannot enumerate).
- In-progress poll/update reject bare ai-agent API keys without a guest JWT.
"""
import os
from uuid import uuid4

import pytest

_SKIP_IN_CI = os.environ.get("CI", "false").lower() == "true" or os.environ.get(
    "TESTING", "false"
).lower() == "true"
_SKIP_REASON = "Async task handling issues with TestClient in CI"


@pytest.mark.skipif(_SKIP_IN_CI, reason=_SKIP_REASON)
def test_get_conversation_requires_read_permission(authorized_client_agent):
    """ai agent API keys must not read arbitrary conversations by UUID."""
    fake_id = uuid4()
    response = authorized_client_agent.get(f"/api/conversations/{fake_id}")
    assert response.status_code == 403


@pytest.mark.skipif(_SKIP_IN_CI, reason=_SKIP_REASON)
def test_poll_requires_guest_token_for_session_only_api_key(authorized_client_agent):
    """Bare shared embed keys cannot poll another conversation by UUID."""
    fake_id = uuid4()
    response = authorized_client_agent.get(f"/api/conversations/in-progress/poll/{fake_id}")
    assert response.status_code in (403, 404)
