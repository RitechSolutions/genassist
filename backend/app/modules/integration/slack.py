import hashlib
import hmac
import time
from typing import Dict, Any, Optional
import logging

from app.core.utils.bi_utils import make_async_web_call

logger = logging.getLogger(__name__)


class SlackApiError(Exception):
    """Raised when the Slack API returns a logical error (``ok: false``)."""


class SlackConnector:

    def __init__(self, token: str, channel: str):
        self.token = token
        self.channel = channel
        self.base_url = "https://slack.com/api"

    async def sanitize_channel(self) -> str:
        """Sanitize the channel name."""
        if (
            isinstance(self.channel, str)
            and "@" in self.channel
            and "." in self.channel
        ):
            user_id = await self.lookup_user_by_email(self.channel)
            if user_id:
                channel_id = await self.open_conversation(user_id)
                if channel_id:
                    self.channel = channel_id
        return self.channel

    async def open_conversation(self, user_id: str) -> str:
        """Open a direct message conversation with a user."""
        url = f"{self.base_url}/conversations.open"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {"users": user_id}

        response = await make_async_web_call(
            method="POST", url=url, headers=headers, payload=payload
        )
        data = response.get("data") or {}
        if response["status"] != 200 or not data.get("ok"):
            slack_error = data.get("error", "unknown_error")
            message = f"Slack: can't open DM with user '{user_id}' ({slack_error})"
            logger.error(message)
            raise SlackApiError(message)
        return data["channel"]["id"]

    async def lookup_user_by_email(self, email: str) -> str:
        """Look up a Slack user by email address."""
        url = f"{self.base_url}/users.lookupByEmail?email={email}"
        headers = {"Authorization": f"Bearer {self.token}"}

        response = await make_async_web_call(
            method="GET", url=url, headers=headers, payload=None
        )
        data = response.get("data") or {}
        if response["status"] != 200 or not data.get("ok"):
            slack_error = data.get("error", "unknown_error")
            message = f"Slack: can't find user by email '{email}' ({slack_error})"
            if slack_error == "missing_scope":
                message += "; bot token needs the 'users:read.email' scope"
            logger.error(message)
            raise SlackApiError(message)
        return data["user"]["id"]

    async def send_slack_message(self, text: str) -> Dict[str, Any]:
        """Send a Slack message to a channel or user."""
        url = f"{self.base_url}/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {"channel": self.channel, "text": text}

        response = await make_async_web_call(
            method="POST", url=url, headers=headers, payload=payload
        )
        data = response.get("data") or {}
        if response["status"] != 200 or not data.get("ok"):
            slack_error = data.get("error", "unknown_error")
            message = (
                f"Slack: can't send to channel '{self.channel}' ({slack_error})"
            )
            logger.error(message)
            raise SlackApiError(message)
        return response

def verify_slack_request(
    request_body: str,
    slack_signature: Optional[str],
    slack_timestamp: Optional[str],
    slack_signature_secret: str,
) -> bool:
    """Verify Slack request signature."""
    if not slack_signature or not slack_timestamp:
        return False

    if abs(time.time() - int(slack_timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{slack_timestamp}:{request_body}".encode("utf-8")
    my_signature = (
        "v0="
        + hmac.new(
            slack_signature_secret.encode("utf-8"), sig_basestring, hashlib.sha256
        ).hexdigest()
    )

    verified = hmac.compare_digest(my_signature, slack_signature)
    return verified
