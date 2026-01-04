from typing import Dict, Any
import logging
import base64

from app.core.utils.bi_utils import make_async_web_call

logger = logging.getLogger(__name__)


class JiraConnector:

    def __init__(self, subdomain: str, email: str, api_token: str):
        self.subdomain = subdomain
        self.email = email
        self.api_token = api_token

    async def create_task(
        self,
        space_key: str,
        task_name: str,
        task_description: str,
    ) -> Dict[str, Any]:
        """Create a Jira task via the REST API."""
        complete_url = f"https://{self.subdomain}/rest/api/3/issue"

        auth_str = f"{self.email}:{self.api_token}"
        auth_bytes = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth_bytes}",
        }

        payload = {
            "fields": {
                "project": {"key": space_key},
                "summary": task_name,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"text": task_description, "type": "text"}],
                        }
                    ],
                },
                "issuetype": {"name": "Task"},
            }
        }

        return await make_async_web_call(
            method="POST", url=complete_url, headers=headers, payload=payload
        )
