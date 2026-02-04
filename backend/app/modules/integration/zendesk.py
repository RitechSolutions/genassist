from typing import Dict, Any, Optional, List, Tuple
from datetime import timedelta
import logging
import httpx
from fastapi import HTTPException

from app.core.config.settings import settings
from app.core.utils.date_time_utils import utc_now

logger = logging.getLogger(__name__)


class ZendeskConnector:
    """
    Centralized Zendesk API connector for all Zendesk operations.
    Supports both default settings-based authentication and custom credentials.
    """

    def __init__(
        self,
        subdomain: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        self.subdomain = subdomain or settings.ZENDESK_SUBDOMAIN
        self.email = email or settings.ZENDESK_EMAIL
        self.api_token = api_token or settings.ZENDESK_API_TOKEN
        self.base_url = f"https://{self.subdomain}/api/v2"
        self.help_center_url = f"https://{self.subdomain}/api/v2/help_center"
        # Ensure api_token is not None for auth tuple
        token = self.api_token or ""
        self._auth: Tuple[str, str] = (f"{self.email}/token", token)

    async def _make_request(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Internal method to make HTTP requests to Zendesk API."""
        async with httpx.AsyncClient(auth=self._auth, timeout=timeout) as client:
            try:
                response = await client.request(method, url, json=json, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Zendesk API error [{e.response.status_code}]: {e.response.text}"
                )
                raise HTTPException(
                    status_code=e.response.status_code, detail="Zendesk API error"
                ) from e
            except httpx.RequestError as e:
                logger.error(f"Network error during Zendesk API call: {e}")
                raise HTTPException(status_code=500, detail="Zendesk API network error") from e

    async def create_ticket(
        self,
        subject: str,
        description: str,
        requester_name: Optional[str] = None,
        requester_email: Optional[str] = None,
        tags: Optional[List[str]] = None,
        custom_fields: Optional[List[Dict[str, Any]]] = None,
        conversation_id: Optional[str] = None,
    ) -> Optional[int]:
        """
        Create a Zendesk ticket via the REST API.
        Returns the ticket ID on success, None on failure.
        """
        if not self.api_token:
            raise ValueError("Zendesk API token is required")
        if not self.email:
            raise ValueError("Zendesk email is required")

        url = f"{self.base_url}/tickets.json"
        payload: Dict[str, Any] = {
            "ticket": {
                "subject": subject,
                "comment": {"body": description, "public": True},
            }
        }

        if requester_name or requester_email:
            payload["ticket"]["requester"] = {}
            if requester_name:
                payload["ticket"]["requester"]["name"] = requester_name
            if requester_email:
                payload["ticket"]["requester"]["email"] = requester_email
            elif not requester_name:
                # Extract name from email if not provided
                payload["ticket"]["requester"]["name"] = (
                    requester_email.split("@")[0] if requester_email else "Unknown"
                )

        if tags:
            payload["ticket"]["tags"] = tags
        if custom_fields:
            payload["ticket"]["custom_fields"] = custom_fields
        # elif conversation_id and settings.ZENDESK_CUSTOM_FIELD_CONVERSATION_ID:
        #     payload["ticket"]["custom_fields"] = [
        #         {
        #             "id": settings.ZENDESK_CUSTOM_FIELD_CONVERSATION_ID,
        #             "value": conversation_id,
        #         }
        #     ]

        try:
            result = await self._make_request("POST", url, json=payload)
            return {"status": 200, "data": result}
        except HTTPException:
            return None

    async def update_ticket(
        self,
        ticket_id: int,
        comment: Optional[str] = None,
        custom_field_updates: Optional[Dict[int, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update an existing Zendesk ticket.
        Can update with a comment, custom fields, or a full payload.
        Returns True on success, False on failure.
        """
        url = f"{self.base_url}/tickets/{ticket_id}.json"

        if payload:
            # Use provided payload directly
            ticket_payload = {"ticket": payload.get("ticket", {})}
        else:
            # Build payload from parameters
            ticket_obj: Dict[str, Any] = {}
            if comment is not None:
                ticket_obj["comment"] = {"body": comment, "public": False}
            if custom_field_updates:
                cf_list = []
                for fld_id, val in custom_field_updates.items():
                    cf_list.append({"id": fld_id, "value": val})
                ticket_obj["custom_fields"] = cf_list
            ticket_payload = {"ticket": ticket_obj}

        try:
            await self._make_request("PUT", url, json=ticket_payload)
            return True
        except HTTPException:
            return False

    async def fetch_ticket_details(
        self, ticket_id: int, include_comments: bool = True
    ) -> Dict[str, Any]:
        """Fetch ticket details from Zendesk. Optionally include comments."""
        url = f"{self.base_url}/tickets/{ticket_id}.json"
        if include_comments:
            url += "?include=comments"

        result = await self._make_request("GET", url)
        return result.get("ticket", {})

    async def post_private_comment(self, ticket_id: int, body: str) -> bool:
        """Post a private comment to a Zendesk ticket."""
        return await self.update_ticket(ticket_id, comment=body)

    async def create_followup_ticket(
        self, original_ticket_id: int, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a followup ticket related to an original ticket."""
        url = f"{self.base_url}/tickets.json"
        # Ensure via_followup_source_id is set
        if "ticket" in payload:
            payload["ticket"]["via_followup_source_id"] = original_ticket_id
        return await self._make_request("POST", url, json=payload)

    async def get_ticket_comments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Get all comments for a ticket."""
        url = f"{self.base_url}/tickets/{ticket_id}/comments.json"
        result = await self._make_request("GET", url)
        return result.get("comments", [])

    async def search_tickets(
        self, query: str, max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for tickets using Zendesk search API.
        Returns a list of tickets matching the query.
        """
        all_results = []
        search_url: Optional[str] = f"{self.base_url}/search.json"
        params = {"query": query}

        while search_url:
            try:
                result = await self._make_request("GET", search_url, params=params)
                results = result.get("results", [])
                all_results.extend(results)

                if max_results and len(all_results) >= max_results:
                    all_results = all_results[:max_results]
                    break

                search_url = result.get("next_page")
                params = {}  # Remove params from next_page URL as it's already included
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.error(f"Error fetching tickets: {e}")
                break

        return all_results

    async def get_unrated_closed_tickets(
        self, days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Fetch all closed, unrated Zendesk tickets (-tags:analyzed) with comments.
        """
        tickets_to_rate = []
        updated_later_then = (
            f" updated>={(utc_now().date() - timedelta(days=days_back)).isoformat()}"
        )
        query_definition = (
            f"type:ticket status:solved status:closed -tags:analyzed {updated_later_then}"
        )

        results = await self.search_tickets(query_definition)

        for ticket in results:
            try:
                ticket_id = ticket["id"]
                if ticket.get("followup_ids") == []:
                    # If followup_ids is [] it means it has Related Ticket where analytics is saved
                    new_ticket = {
                        "id": ticket_id,
                        "created_at": ticket.get("created_at"),
                        "subject": ticket.get("raw_subject"),
                        "description": ticket.get("description"),
                        "status": ticket.get("status"),
                        "tags": ticket.get("tags"),
                        "transcription": [],
                    }

                    # Get comments for this ticket
                    comments = await self.get_ticket_comments(ticket_id)
                    from app.core.utils.enums.transcript_message_type import (
                        TranscriptMessageType,
                    )

                    for comment in comments:
                        new_comment = {
                            "id": comment.get("id"),
                            "timestamp": comment.get("created_at"),
                            "message": comment.get("plain_body"),
                            "type": TranscriptMessageType.MESSAGE.value,
                        }
                        new_ticket["transcription"].append(new_comment)

                    tickets_to_rate.append(new_ticket)
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Error processing ticket ID {ticket.get('id')}: {e}")
                continue

        return tickets_to_rate

    async def fetch_articles(
        self,
        locale: Optional[str] = None,
        section_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all articles from Zendesk Help Center.
        Args:
            locale: Optional locale filter (e.g., "en-us")
            section_id: Optional section ID to filter articles
        Returns:
            List of article dictionaries
        """
        all_articles = []
        url: Optional[str] = f"{self.help_center_url}/articles.json"

        if section_id:
            url = f"{self.help_center_url}/sections/{section_id}/articles.json"

        params = {}
        if locale:
            params["locale"] = locale

        while url:
            try:
                result = await self._make_request("GET", url, params=params, timeout=30.0)
                articles = result.get("articles", [])
                all_articles.extend(articles)

                # Check for next page
                url = result.get("next_page")
                if url:
                    # Remove params from next_page URL as it's already included
                    params = {}

                logger.info(
                    f"Fetched {len(articles)} articles from Zendesk (total: {len(all_articles)})"
                )
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.error(f"Error fetching articles: {e}")
                break

        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles
