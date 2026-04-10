import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

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
        raw = (subdomain or settings.ZENDESK_SUBDOMAIN or "").strip()
        # Normalize subdomain: ensure it has .zendesk.com (matches connection_tester)
        if not raw:
            self.subdomain = ""
        elif raw.endswith(".zendesk.com"):
            self.subdomain = raw
        else:
            self.subdomain = f"{raw}.zendesk.com"

        self.email = email or settings.ZENDESK_EMAIL
        self.api_token = api_token or settings.ZENDESK_API_TOKEN
        self.base_url = f"https://{self.subdomain}/api/v2"
        self.help_center_url = f"https://{self.subdomain}/api/v2/help_center"
        # Ensure api_token is not None for auth tuple
        token = self.api_token or ""
        self._auth: Tuple[str, str] = (f"{self.email}/token", token)
        self.page_size = 50

    async def _make_request(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Internal method to make HTTP requests to Zendesk API.
        Uses trust_env=True so HTTP_PROXY/HTTPS_PROXY from env are respected (e.g. in Celery worker).
        """
        async with httpx.AsyncClient(
            auth=self._auth,
            timeout=timeout,
            trust_env=True,  # Use HTTP_PROXY/HTTPS_PROXY from environment
            follow_redirects=True,
        ) as client:
            try:
                response = await client.request(method, url, json=json, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Zendesk API error [{e.response.status_code}]: {e.response.text}"
                )
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=e.response.text,
                ) from e
            except httpx.RequestError as e:
                logger.error(
                    "Zendesk network error (check worker outbound access, proxy, DNS): %s",
                    e,
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Zendesk API network error: {type(e).__name__}: {e}",
                ) from e

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

    @staticmethod
    async def test_connection(cd: dict) -> dict:
        """Test Zendesk connectivity using the /users/me endpoint."""
        subdomain = cd.get("subdomain", "")
        if not subdomain.endswith(".zendesk.com"):
            subdomain = f"{subdomain}.zendesk.com"
        connector = ZendeskConnector(
            subdomain=subdomain,
            email=cd.get("email"),
            api_token=cd.get("api_token"),
        )
        await connector._make_request("GET", f"{connector.base_url}/users/me.json")
        return {"success": True, "message": "Successfully connected to Zendesk."}

    async def _fetch_articles_paginated(
        self, start_url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        all_articles: List[Dict[str, Any]] = []
        base_params = dict(params) if params else {}
        # Zendesk HC list endpoints default to 30/page. Keep per_page constant across pages.
        per_page = int(base_params.get("per_page") or self.page_size)
        page = int(base_params.get("page") or 1)

        page_count: Optional[int] = None
        while page_count is None or page <= page_count:
            try:
                before = len(all_articles)
                page_params = {**base_params, "per_page": per_page, "page": page}
                result = await self._make_request(
                    "GET", start_url, params=page_params, timeout=30.0
                )

                articles = result.get("articles", [])
                all_articles.extend(articles)
                next_page = result.get("next_page")
                try:
                    page_count = int(result.get("page_count") or page_count or 0) or None
                except (TypeError, ValueError):
                    page_count = page_count

                # Safety: stop if a page returns nothing new (prevents infinite loops on bad metadata).
                if len(all_articles) == before:
                    logger.warning(
                        "Zendesk:No pagination progress; stopping",
                        extra={
                            "page": page,
                            "page_count": page_count,
                            "per_page": per_page,
                            "total_articles": len(all_articles),
                        },
                    )
                    break
                logger.info(
                    "Zendesk:Fetched %d articles from Zendesk (total: %d)",
                    len(articles),
                    len(all_articles),
                    extra={
                        "page": page,
                        "page_count": page_count,
                        "per_page": per_page,
                        "next_page": next_page,
                    },
                )
                page += 1
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.error(f"Zendesk:Error fetching articles: {e}")
                logger.error(f"Zendesk:Error fetching articles: {e}", exc_info=True)
                break
        return all_articles

    async def fetch_articles(
        self,
        locale: Optional[str] = None,
        category_ids: Optional[List[int]] = None,
        section_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch all articles from Zendesk Help Center.
        Args:
            locale: Optional locale filter (e.g., "en-us")
            category_ids: Optional category IDs to filter articles (merged, de-duplicated by id)
            section_id: Optional section ID to filter articles
        Returns:
            List of article dictionaries
        """

        base_url = f"{self.help_center_url}/{locale}" if locale else self.help_center_url
        logger.info("Zendesk:Base URL: %s", base_url)

        if section_id:
            start_url = f"{base_url}/sections/{section_id}/articles.json"
            logger.debug("Fetching articles from section ID", {"section_id": section_id})
            all_articles = await self._fetch_articles_paginated(start_url)
        elif category_ids:
            seen_ids: set[Any] = set()
            all_articles = []
            # Dedupe IDs; dict.fromkeys preserves first-seen order (set() does not).
            unique_category_ids = list(dict.fromkeys(category_ids))
            sem = asyncio.Semaphore(10)

            # Fetch articles from one category
            async def _fetch_one_category(cid: int) -> List[Dict[str, Any]]:
                start_url = f"{base_url}/categories/{cid}/articles.json"
                logger.info("Zendesk:Category Id: %s", cid)
                logger.debug("Fetching articles from category ID", {"category_id": cid})
                async with sem:
                    return await self._fetch_articles_paginated(start_url)

            batches = await asyncio.gather(
                *[_fetch_one_category(cid) for cid in unique_category_ids]
            )
            for batch in batches:
                for article in batch:
                    aid = article.get("id")
                    if aid is not None:
                        if aid in seen_ids:
                            continue
                        seen_ids.add(aid)
                    all_articles.append(article)
        else:
            all_articles = await self._fetch_articles_paginated(
                f"{self.help_center_url}/articles.json"
            )

        logger.info(f"Zendesk:Total articles fetched: {len(all_articles)}")
        return all_articles
