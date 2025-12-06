from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
import httpx
import requests
import logging
from msal import ConfidentialClientApplication
from urllib.parse import quote, urlparse, unquote
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException


logger = logging.getLogger(__name__)


class Office365Connector:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        refresh_token: str,
        redirect_uri: str,
        sharepoint_url: str = None,
        site_id: str =None,
        drive_id: str = None,
        access_token: str = None,
        for_sharepoint = True

    ):
        self.site_id = site_id
        self.drive_id = drive_id
        self.folder_path=""
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id 
        self.refresh_token = refresh_token
        self.redirect_uri = redirect_uri
        self.sharepoint_url = sharepoint_url
        self.access_token = access_token or self.refresh_access_token()
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        self.for_sharepoint = for_sharepoint
        self._client: httpx.AsyncClient | None = None

        if (self.site_id is None or self.drive_id is None) and self.for_sharepoint:
            self.resolve_sharepoint_url(self.sharepoint_url)

    def refresh_access_token(self) -> str:

        auth_client = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}"
            )
        
        result = auth_client.acquire_token_by_refresh_token(
            refresh_token=self.refresh_token,
            scopes=[
                "https://graph.microsoft.com/Files.Read",
                "https://graph.microsoft.com/Sites.Read.All",
                "https://graph.microsoft.com/Calendars.ReadWrite"
            ]
            )

        if "access_token" in result:
            new_token = result["access_token"]
            self.access_token = new_token
            logger.info("Successfully refreshed access token.")
            # print("Access token:", result["access_token"])
            return new_token
        else:
            print("Error:", result.get("error_description"))
            
        
        
        # logger.info("Refreshing Microsoft Graph access token...")
        # token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

        # data = {
        #     "client_id": self.client_id,
        #     "client_secret": self.client_secret,
        #     "refresh_token": self.refresh_token,
        #     "grant_type": "refresh_token",
        #     "redirect_uri": self.redirect_uri,
        #     "scope": "offline_access https://graph.microsoft.com/User.Read",
        # }

        # headers = {
        #     "Content-Type": "application/x-www-form-urlencoded",
        # }

        # response = requests.post(token_url, data=data, headers=headers)

        # if response.status_code != 200:
        #     logger.error(f"Failed to refresh token: {response.status_code} - {response.text}")
        #     raise Exception("Unable to refresh access token")

        # token_data = response.json()
        # new_token = token_data["access_token"]
        # self.access_token = new_token
        # #self.headers["Authorization"] = f"Bearer {new_token}"
        # logger.info("Successfully refreshed access token.")
        # return new_token

    def list_files(self, folder_path: Optional[str] = None) -> dict:
        """
        Recursively list all files in the specified SharePoint folder.
        folder_path = "Shared Documents/MyFolder"
        """
        if folder_path==None:
            folder_path=self.folder_path
        logger.info(f"Listing files from folder (recursively): {folder_path}")
        files = []
        self._list_files_recursive(folder_path, files)
        return {"files": files}

    def _list_files_recursive(self, folder_path: str, files_accumulator: list):
        url=f"{self.base_url}/sites/{self.site_id}/drives/{self.drive_id}/root:/{folder_path}:/children"

        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            raise Exception(f"Error listing folder {folder_path}: {response.text}")

        for item in response.json().get("value", []):
            if "folder" in item:
                sub_path = f"{folder_path}/{item['name']}"
                self._list_files_recursive(sub_path, files_accumulator)
            elif "file" in item:
                files_accumulator.append({
                    "name": item["name"],
                    "path": f"{folder_path}/{item['name']}",
                    "download_url": item["@microsoft.graph.downloadUrl"]
                })

    def get_file_content(self, download_url: str):
        response = requests.get(download_url)
        if response.status_code != 200:
            raise Exception(f"Error downloading file: {response.status_code} - {response.text}")
        return response.content


    def resolve_sharepoint_url(self, sharepoint_url: str):
        """
        Resolves a SharePoint folder URL to Microsoft Graph-compatible site_id, drive_id, and folder_path.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        # Parse and clean up the SharePoint URL
        parsed = urlparse(sharepoint_url)
        hostname = parsed.hostname  # e.g., netorgft1993465.sharepoint.com
        path_parts = parsed.path.split('/')
        
        # Identify site name and folder path
        try:
            site_index = path_parts.index("sites")
            site_path = "/".join(path_parts[site_index:site_index + 2])  # e.g., sites/GenAssist_sharepoint
        except ValueError:
            raise Exception("Invalid SharePoint URL: cannot find 'sites/<site-name>' path.")

        # Step 1: Get site ID
        site_resp = requests.get(
            f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{site_path}",
            headers=headers
        )
        site_resp.raise_for_status()
        self.site_id = site_resp.json()["id"]

        # Step 2: Get drive ID (default is 'Documents' or 'Shared Documents')
        drives_resp = requests.get(
            f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives",
            headers=headers
        )
        drives_resp.raise_for_status()

        drives = drives_resp.json()["value"]
        doc_drive = next((d for d in drives if d["name"] in ["Documents", "Shared Documents"]), None)

        if not doc_drive:
            raise Exception("Default document library not found.")

        self.drive_id = doc_drive["id"]

        # Step 3: Extract folder path after 'Shared Documents'
        raw_path = unquote(parsed.path)  # decode %20 etc.
        try:
            folder_root_index = raw_path.index("Shared Documents")
            folder_path = raw_path[folder_root_index + len("Shared Documents/"):]
        except ValueError:
            raise Exception("Could not locate 'Shared Documents' in the URL.")

        self.folder_path = folder_path.strip("/")


    @asynccontextmanager
    async def _session(self):
        """
        Lazy-init a shared AsyncClient and auto-close it when
        the Office365Connector instance gets GC-collected.
        Usage:   async with self._session() as client: ...
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=20.0)
        try:
            yield self._client
        finally:
            pass  # caller closes; see __del__


    async def __aexit__(self, *exc):
        if self._client:
            await self._client.aclose()


    async def create_calendar_event(
            self,
            summary: str,
            start: datetime,
            end: datetime,
            timezone: str = "UTC",
            content: str | None = None,
            location: str | None = None,
            attendees: list[str] | None = None,
            online_meeting: bool = False,
            ) -> dict:
        self._ensure_token()

        url = f"{self.base_url}/me/events"
        payload = {
            "subject": summary,
            "body": {"contentType": "HTML", "content": content or ""},
            "start": {"dateTime": start.isoformat(timespec='seconds'), "timeZone": timezone},
            "end": {"dateTime": end.isoformat(timespec='seconds'), "timeZone": timezone},
            "location": {"displayName": location or ""},
            "attendees": [
                {"emailAddress": {"address": mail, "name": mail}, "type": "required"}
                for mail in (attendees or [])
                ],
            "allowNewTimeProposals": True,
            "isOnlineMeeting": online_meeting,
            "onlineMeetingProvider": "teamsForBusiness" if online_meeting else None,
            }
        payload = {k: v for k, v in payload.items() if v is not None}

        async with self._session() as client:
            resp = await client.post(
                    url,
                    headers={**self.headers, "Content-Type": "application/json"},
                    json=payload,
                    )

        if resp.status_code >= 300:
            logger.error(f"Failed to create calendar event: {resp.status_code} - {resp.text}")
            raise AppException(
                    error_key=ErrorKey.FAIL_CREATE_EVENT_OFFICE_365,
                    status_code=500,
                    error_detail=resp.text,
                    )

        return resp.json()


    async def list_calendar_events(
            self,
            *,
            start: datetime,
            end: datetime,
            subject_contains: str | None = None,
            attendee: str | None = None,
            top: int = 100,
            timezone: str = "UTC",
            return_raw: bool = False,
            ):

        self._ensure_token()

        if top > 100:
            raise AppException(ErrorKey.TOO_MANY_RESULTS
                               )
        prefer_hdr = f'outlook.timezone="{timezone}"'

        #  Build the base params dict – httpx will URL-encode for us
        params = {
            "startDateTime": start.isoformat(timespec="seconds"),
            "endDateTime": end.isoformat(timespec="seconds"),
            "$orderby": "start/dateTime",
            "$top": top,
            }

        # Server-side filter
        filters = []
        if subject_contains:
            sanitized = subject_contains.replace("'", "''")  # OData single-quote escape
            filters.append(f"contains(subject,'{sanitized}')")

        if attendee:
            filters.append(
                    f"attendees/any(a:a/emailAddress/address eq '{attendee.lower()}')"
                    )
        if filters:
            params["$filter"] = " and ".join(filters)


        events: list[dict] = []
        next_url: str | None = f"{self.base_url}/me/calendarView"

        async with self._session() as client:
            while next_url:
                resp = await client.get(
                        next_url,
                        headers={**self.headers, "Prefer": prefer_hdr},
                        params=params if next_url.endswith("calendarView") else None,  # only first call
                        )
                if resp.status_code >= 300:
                    logger.error(f"List events failed: {resp.status_code} - {resp.text}")
                    raise AppException(
                            error_key=ErrorKey.FAIL_SEARCH_EVENT_OFFICE_365,
                            status_code=500,
                            error_detail=resp.text,
                            )
                data = resp.json()
                events.extend(data.get("value", []))
                next_url = data.get("@odata.nextLink")

        return events if return_raw else [
        {
            "id": e["id"],
            "subject": e.get("subject", ""),
            "start": e["start"],
            "end": e["end"],
            "location": e.get("location", {}).get("displayName", ""),
            "webLink": e.get("webLink"),
            "isOnline": e.get("isOnlineMeeting", False),
            }
        for e in events
        ]


    # ensure token helper
    def _ensure_token(self):
        if not self.access_token:
            self.refresh_access_token()
        self.headers["Authorization"] = f"Bearer {self.access_token}"
