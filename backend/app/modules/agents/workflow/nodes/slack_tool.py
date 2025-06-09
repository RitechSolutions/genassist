import logging
import json
from typing import Dict, Any
import aiohttp
from app.modules.agents.workflow.base_processor import NodeProcessor
from app.core.utils.string_utils import replace_template_vars

logger = logging.getLogger(__name__)


class SlackMessageNodeProcessor(NodeProcessor):
    """Processor for sending Slack messages to users/channels or channels.
the expected input for process is:

{
    "slack_token":"x",
    "slack_channel":"y",
    "slack_message","hello world"
}
    """

    async def send_slack_message(self, token: str, channel: str, text: str) -> Dict[str, Any]:
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "channel": channel,
            "text": text
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                try:
                    response.raise_for_status()
                    return {
                        "status": response.status,
                        "data": await response.json()
                    }
                except Exception as e:
                    logger.error(f"Slack message failed: {e}")
                    return {
                        "status": response.status,
                        "data": {"error": str(e)}
                    }
                
    async def lookup_user_by_email(self, token: str, email: str) -> str:            
        """If is provided only email and not user channel/id then """
        url = f"https://slack.com/api/users.lookupByEmail?email={email}"
        headers = {
            "Authorization": f"Bearer {token}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                if not data.get("ok"):
                    logger.error(f"Slack Error or user not found: {email}")
                    return None
                return data["user"]["id"]


    async def open_conversation(self, token: str, user_id: str) -> str:
        url = "https://slack.com/api/conversations.open"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "users": user_id
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()
                if not data.get("ok"):
                    # raise HTTPException(status_code=400, detail=data.get("error", "Slack API error"))
                    logger.error(f"Slack Error opening conversation with user: {user_id}")
                    return {
                        "status": response.status,
                        "data": {"error": str(user_id)}
                    }
                return data["channel"]["id"]

    async def process(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:

        token = input_data.get("token")
        channel = input_data.get("channel")

        if isinstance(channel, str) and "@" in channel and "." in channel:
            # read user_id from email
            user_id= await self.lookup_user_by_email(token, channel)
            if user_id:
                channel_id = await self.open_conversation(token, user_id)
                if channel_id:
                    channel = channel_id

        text = input_data.get("text") if input_data else None

        if not token or not channel or not text:
            error_msg = "SlackMessageNodeProcessor: Missing token, channel, or message"
            logger.error(error_msg)
            self.output = {
                "status": 400,
                "data": {"error": error_msg}
            }
            return self.output

        response = await self.send_slack_message(token, channel, text)
        self.save_output(response)
        return response
