"""SalesForce API connector.

Centralised connector for SalesForce operations used by the workflow engine's
SalesForce Case node. Mirrors :class:`ZendeskConnector` in transport behaviour
(httpx, ``trust_env``, ``raise_for_status``, errors wrapped in ``HTTPException``)
while authenticating via the OAuth2 **client-credentials** flow (app-level auth —
just client id + secret; the Connected App runs as its configured "Run As" user)
and creating SalesForce **Case** records.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.core.config.settings import settings

logger = logging.getLogger(__name__)

# SalesForce REST API version used for the sobjects endpoint.
SALESFORCE_API_VERSION = "v60.0"


class SalesforceConnector:
    """SalesForce REST API connector (OAuth2 client-credentials grant, Case creation).

    Supports both default settings-based credentials and per-tenant credentials
    supplied from App Settings.
    """

    def __init__(
        self,
        instance_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.instance_url = (
            instance_url or getattr(settings, "SALESFORCE_INSTANCE_URL", None) or ""
        ).rstrip("/")
        self.client_id = client_id or getattr(settings, "SALESFORCE_CLIENT_ID", None)
        self.client_secret = client_secret or getattr(
            settings, "SALESFORCE_CLIENT_SECRET", None
        )
        # Resolved after a successful token exchange (the org may redirect to a
        # pod-specific host, which we prefer over the configured instance URL).
        self._access_token: Optional[str] = None
        self._token_instance_url: Optional[str] = None

    async def _make_request(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Make an HTTP request to SalesForce.

        Uses ``trust_env=True`` so HTTP_PROXY/HTTPS_PROXY from the environment are
        respected (e.g. inside a Celery worker). Errors are wrapped in
        ``HTTPException`` exactly like :class:`ZendeskConnector`.
        """
        async with httpx.AsyncClient(
            timeout=timeout,
            trust_env=True,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.request(
                    method, url, json=json, data=data, headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"SalesForce API error [{e.response.status_code}]: {e.response.text}"
                )
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=e.response.text,
                ) from e
            except httpx.RequestError as e:
                logger.error(
                    "SalesForce network error (check worker outbound access, proxy, DNS): %s",
                    e,
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"SalesForce API network error: {type(e).__name__}: {e}",
                ) from e

    async def _get_access_token(self) -> str:
        """Authenticate via the OAuth2 **client-credentials** grant.

        Only the Connected App's client id + secret are needed; SalesForce runs the
        request as the Connected App's configured "Run As" user. Stores and returns
        the ``access_token``; also records the ``instance_url`` returned by SalesForce
        (preferred for subsequent API calls).
        """
        if not self.instance_url:
            raise ValueError("SalesForce instance URL is required")
        if not self.client_id or not self.client_secret:
            raise ValueError("SalesForce client id and client secret are required")

        token_url = f"{self.instance_url}/services/oauth2/token"
        form_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        result = await self._make_request(
            "POST",
            token_url,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        access_token = result.get("access_token")
        if not access_token:
            raise ValueError("SalesForce OAuth2 response did not include an access_token")

        self._access_token = access_token
        # Prefer the instance URL returned by the token response over the configured one.
        self._token_instance_url = (result.get("instance_url") or self.instance_url).rstrip("/")
        return access_token

    async def create_case(
        self,
        subject: str,
        description: str,
        custom_fields: Optional[List[Dict[str, Any]]] = None,
        labels: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a SalesForce Case via the REST API.

        Returns ``{"status": 200, "data": result}`` on success. On an API/auth
        failure it returns ``{"status": <sf status>, "data": {"error": <detail>}}`` so
        the real SalesForce error (e.g. ``invalid_client``) reaches the caller instead
        of being flattened into an opaque 500.

        Beyond ``Subject`` and ``Description``, any additional Case fields (priority,
        origin, custom fields, …) are set via ``custom_fields``: an
        ``Array<{"key": str, "value": str}>`` mapped onto the Case body by Case field
        **API name** (``key`` → ``value``).

        ``labels`` are assigned as SalesForce **Topics** after the Case is created
        (find-or-create the Topic by name, then link it via ``TopicAssignment``).
        Topic assignment is best-effort: a failure is logged and does not undo the
        already-created Case (requires *Topics for Objects* enabled on Case).
        """
        try:
            access_token = await self._get_access_token()
            instance_url = self._token_instance_url or self.instance_url
            url = f"{instance_url}/services/data/{SALESFORCE_API_VERSION}/sobjects/Case"

            payload: Dict[str, Any] = {
                "Subject": subject,
                "Description": description,
            }
            if custom_fields:
                for field in custom_fields:
                    key = field.get("key")
                    if key:
                        payload[key] = field.get("value")

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            result = await self._make_request("POST", url, json=payload, headers=headers)

            case_id = result.get("id") if isinstance(result, dict) else None
            if labels and case_id:
                await self._assign_topics(case_id, labels, access_token, instance_url)

            return {"status": 200, "data": result}
        except HTTPException as e:
            return {"status": e.status_code, "data": {"error": e.detail}}

    async def _assign_topics(
        self, case_id: str, labels: List[str], access_token: str, instance_url: str
    ) -> None:
        """Assign each label to the Case as a Topic (best-effort, per-label).

        Finds or creates the Topic by name, then inserts a ``TopicAssignment``
        linking it to the Case. A per-label failure is logged and skipped so one bad
        label (or Topics being disabled) never undoes the created Case.
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        base = f"{instance_url}/services/data/{SALESFORCE_API_VERSION}"
        for raw in labels:
            name = (raw or "").strip()
            if not name:
                continue
            try:
                topic_id = await self._get_or_create_topic(name, headers, base)
                if not topic_id:
                    continue
                await self._make_request(
                    "POST",
                    f"{base}/sobjects/TopicAssignment",
                    json={"EntityId": case_id, "TopicId": topic_id},
                    headers=headers,
                )
            except HTTPException as exc:
                logger.warning(
                    "SalesForce: failed to assign label '%s' as a Topic (is 'Topics for "
                    "Objects' enabled on Case?): %s",
                    name,
                    exc.detail,
                )

    async def _get_or_create_topic(
        self, name: str, headers: Dict[str, Any], base: str
    ) -> Optional[str]:
        """Return the Id of the Topic named ``name``, creating it if it doesn't exist.

        Idempotent under concurrency: ``Topic.Name`` is unique, so if two runs create
        the same new Topic at once one gets a ``DUPLICATE_VALUE`` error — in that case
        we re-query and use the Topic the other run created rather than losing the label.
        """
        topic_id = await self._find_topic(name, headers, base)
        if topic_id:
            return topic_id

        try:
            created = await self._make_request(
                "POST", f"{base}/sobjects/Topic", json={"Name": name}, headers=headers
            )
            return created.get("id") if isinstance(created, dict) else None
        except HTTPException as exc:
            # Lost a create race (or the name already existed) — re-fetch.
            if "DUPLICATE" in str(exc.detail).upper():
                return await self._find_topic(name, headers, base)
            raise

    async def _find_topic(
        self, name: str, headers: Dict[str, Any], base: str
    ) -> Optional[str]:
        """Look up a Topic Id by exact name (returns None if not found)."""
        # Escape for SOQL string literal (backslash then single-quote).
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        soql = f"SELECT Id FROM Topic WHERE Name = '{escaped}' LIMIT 1"
        query = await self._make_request(
            "GET", f"{base}/query/?q={quote(soql)}", headers=headers
        )
        records = query.get("records") or []
        return records[0].get("Id") if records else None

    @staticmethod
    async def test_connection(cd: dict) -> dict:
        """Test SalesForce connectivity by performing the OAuth2 client-credentials grant.

        Async because the ``DataSourceService.test_connection`` dispatch awaits it.
        """
        connector = SalesforceConnector(
            instance_url=cd.get("salesforce_instance_url") or cd.get("instance_url"),
            client_id=cd.get("salesforce_client_id") or cd.get("client_id"),
            client_secret=cd.get("salesforce_client_secret") or cd.get("client_secret"),
        )
        await connector._get_access_token()
        return {"success": True, "message": "Successfully connected to SalesForce."}
