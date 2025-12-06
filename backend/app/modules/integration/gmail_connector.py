import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime, timedelta
from uuid import UUID
from fastapi import HTTPException

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.encryption_utils import decrypt_key
from app.dependencies.injector import injector
from app.schemas.datasource import DataSourceUpdate
from app.services.app_settings import AppSettingsService
from app.services.datasources import DataSourceService

# Google API imports
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests

logger = logging.getLogger(__name__)


class GmailConnector:
    """
    Gmail API connector for sending and retrieving emails
    """

    # Gmail API scopes
    # I have seen they are implemented in frontend, so I will comment out for now
    # SCOPES = [
    #     'https://www.googleapis.com/auth/gmail.send',
    #     'https://www.googleapis.com/auth/gmail.readonly',
    #     'https://www.googleapis.com/auth/gmail.modify'
    #     "https://www.googleapis.com/auth/calendar.events"
    # ]

    def __init__(self, ds_id: UUID):
        """
        Initialize Gmail connector
        """

        self.service = None
        self.current_access_token = None
        self.refresh_token = None
        self.expires_at = None
        self.client_id = ""
        self.client_secret = ""
        self.ds_id = ds_id

    async def _initialize_service(self):
        try:
            ds_service = injector.get(DataSourceService)
            ds = await ds_service.get_by_id(self.ds_id, decrypt_sensitive=True)
            if not ds:
                logger.error(f"Cant find gmail datasource with id: {self.ds_id}")
                return
            logger.info(f"Connection data: {ds}")

            self.current_access_token = ds.connection_data.get("access_token")
            self.refresh_token = ds.connection_data.get("refresh_token")
            self.expires_at = datetime.fromisoformat(
                ds.connection_data.get("expires_at")
            )

            logger.info(f"Read Gmail tokens from connection data.")

            # Get app_settings_id from data source connection_data
            app_settings_id = ds.connection_data.get("app_settings_id")
            if not app_settings_id:
                raise Exception("App settings ID not found in data source")

            # Get Gmail credentials from app settings by ID
            settings_service = injector.get(AppSettingsService)
            app_settings = await settings_service.get_by_id(UUID(app_settings_id))

            # Extract values from the values field
            values = (
                app_settings.values if isinstance(app_settings.values, dict) else {}
            )
            client_id = values.get("gmail_client_id")
            client_secret = values.get("gmail_client_secret")

            # Decrypt client_secret
            if client_secret:
                client_secret = decrypt_key(client_secret)

            if not client_id:
                raise Exception("gmail_client_id not found in app settings!")

            if not client_secret:
                raise Exception("gmail_client_secret not found in app settings!")

            self.client_id = client_id
            self.client_secret = client_secret

            creds = Credentials(
                token=self.current_access_token,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            self.service = build("gmail", "v1", credentials=creds)

            self.calendar_service = build("calendar", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Could not initialize service: {e}")

    async def get_gmail_tokens(self) -> Optional[Dict[str, str]]:
        """
        Get Gmail tokens from app settings and refresh if expired
        """
        try:
            if not self.service:
                await self._initialize_service()

            if not self.current_access_token and not self.refresh_token:
                logger.warning("Gmail tokens not found in app settings")
                return None
            if self.current_access_token and self.expires_at:
                # Check if current token is still valid
                if datetime.now() < self.expires_at:
                    return {
                        "access_token": self.current_access_token,
                        "refresh_token": self.refresh_token,
                    }

            # Check if access token is expired or will expire soon (5 minutes buffer)
            current_time = datetime.now()

            if self.expires_at:
                try:
                    # Parse expiration time (assuming ISO format or timestamp)
                    # if self.expires_at.isdigit():
                    # Unix timestamp
                    # self.expires_at = datetime.fromtimestamp(int(gmail_token_expires_at.value))
                    # else:
                    # ISO format
                    # expires_at = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))

                    # Add 5-minute buffer to refresh before actual expiration
                    if current_time >= (self.expires_at - timedelta(minutes=5)):
                        logger.info(
                            "Gmail access token expired or expiring soon, refreshing..."
                        )
                        refreshed_tokens = self._refresh_gmail_token(self.refresh_token)

                        if refreshed_tokens:
                            from app.dependencies.injector import injector

                            self.ds_service = injector.get(DataSourceService)

                            # Update tokens in app settings
                            await self._save_refreshed_tokens(refreshed_tokens)

                            self.current_access_token = refreshed_tokens["access_token"]
                            self.refresh_token = refreshed_tokens.get(
                                "refresh_token", self.refresh_token
                            )
                            self.expires_at = datetime.fromisoformat(
                                refreshed_tokens["expires_at"]
                            )
                            return refreshed_tokens
                        else:
                            logger.error("Failed to refresh Gmail token")
                            return None
                    else:
                        logger.info("Gmail access token is still valid")

                        return {
                            "access_token": self.current_access_token,
                            "refresh_token": self.refresh_token,
                        }

                except (ValueError, AttributeError) as e:
                    logger.warning(
                        f"Invalid token expiration format: {e}, attempting refresh"
                    )
                    # If we can't parse expiration, try to refresh anyway
                    refreshed_tokens = self._refresh_gmail_token(self.refresh_token)

                    if refreshed_tokens:
                        await self._save_refreshed_tokens(refreshed_tokens)
                        self.current_access_token = refreshed_tokens["access_token"]
                        self.refresh_token = refreshed_tokens.get(
                            "refresh_token", self.refresh_token
                        )
                        self.expires_at = datetime.fromisoformat(
                            refreshed_tokens["expires_at"]
                        )
                        return refreshed_tokens
            else:
                # No expiration info stored, try to validate current token
                logger.info(
                    "No token expiration info found, validating current token..."
                )
                if not self._validate_gmail_token(self.refresh_token):
                    logger.info("Gmail access token is invalid, refreshing...")
                    refreshed_tokens = self._refresh_gmail_token(self.refresh_token)

                    if refreshed_tokens:
                        self._save_refreshed_tokens(refreshed_tokens)
                        self.current_access_token = refreshed_tokens["access_token"]
                        self.refresh_token = refreshed_tokens.get(
                            "refresh_token", self.refresh_token
                        )
                        self.expires_at = datetime.fromisoformat(
                            refreshed_tokens["expires_at"]
                        )
                        return refreshed_tokens
                    else:
                        logger.error("Failed to refresh Gmail token")
                        return None

            # Token is still valid
            return {"access_token": self.current_access_token}

        except Exception as e:
            logger.error(f"Failed to get Gmail tokens: {e}")
            return None

    def _refresh_gmail_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Refresh Gmail access token using refresh token
        """
        try:
            # Google OAuth2 token refresh endpoint
            token_url = "https://oauth2.googleapis.com/token"

            if not self.client_id or not self.client_secret:
                logger.error("Google client credentials not found")
                return None

            payload = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            response = requests.post(token_url, data=payload)
            response.raise_for_status()

            token_data = response.json()

            # Calculate expiration time
            expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
            expires_at = datetime.now() + timedelta(seconds=expires_in)

            refreshed_tokens = {
                "access_token": token_data["access_token"],
                "refresh_token": refresh_token,  # Refresh token usually stays the same
                "expires_at": expires_at.isoformat(),
            }

            # Some responses include a new refresh token
            if "refresh_token" in token_data:
                refreshed_tokens["refresh_token"] = token_data["refresh_token"]

            logger.info("Gmail access token refreshed successfully")
            return refreshed_tokens

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh Gmail token: {e}")
            return None
        except KeyError as e:
            logger.error(f"Invalid token response format: {e}")
            return None

    def _validate_gmail_token(self) -> bool:
        """
        Validate Gmail access token by making a test API call
        """
        try:
            # Simple API call to validate token
            logger.info("Fetching user email from Gmail profile")
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {self.current_access_token}"}
            response = requests.request("GET", user_info_url, headers=headers)
            if response.status_code != 200:
                logger.error(
                    f"Failed to retrieve user info: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=400, detail="Failed to retrieve user information"
                )
            return True

        except requests.exceptions.RequestException:
            return False

    async def _save_refreshed_tokens(self, tokens: Dict[str, str]):
        """
        Save refreshed tokens back to app settings
        """
        try:
            ds = await self.ds_service.get_by_id(self.ds_id)
            if not ds:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Data source with ID {self.ds_id} not found",
                )

            existing_data = ds.connection_data
            existing_data["access_token"] = tokens["access_token"]
            existing_data["refresh_token"] = tokens.get(
                "refresh_token", existing_data["refresh_token"]
            )
            existing_data["expires_at"] = tokens.get(
                "expires_at", existing_data["expires_at"]
            )

            ds_update = DataSourceUpdate(
                name=ds.name,
                source_type=ds.source_type,
                is_active=ds.is_active,
                connection_data=existing_data,
            )

            # Update access token
            await self.ds_service.update(self.ds_id, ds_update)

            await self._initialize_service()

            logger.info("Gmail tokens updated in app settings")

        except Exception as e:
            logger.error(f"Failed to save refreshed tokens: {e}")

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send email via Gmail

        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            attachments: List of file paths to attach (optional)
            access_token: Optional access token for this operation

        Returns:
            Dict with send result information
        """

        await self.get_gmail_tokens()

        if not self._validate_gmail_token():
            return {
                "success": False,
                "error": "Failed to authenticate with Gmail API",
                "status": "authentication_failed",
                "to": to,
                "subject": subject,
            }

        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["to"] = to
            message["subject"] = subject

            if cc:
                message["cc"] = ", ".join(cc)
            if bcc:
                message["bcc"] = ", ".join(bcc)

            # Add plain text part
            text_part = MIMEText(body, "plain")
            message.attach(text_part)

            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, "html")
                message.attach(html_part)

            if attachments:
                logger.info(f"Processing {len(attachments)} attachments")
                for i, attachment_info in enumerate(attachments):
                    if isinstance(attachment_info, dict):
                        filename = attachment_info.get("name")
                        file_data = attachment_info.get("file", {})

                        if not filename or not file_data:
                            logger.warning(
                                f"Skipping attachment {i}: missing filename or file_data"
                            )
                            continue

                        base64_content = file_data.get("content")
                        if base64_content:
                            try:
                                logger.info(f"Processing attachment: {filename}")
                                logger.info(
                                    f"Base64 content length: {len(base64_content)}"
                                )

                                file_content = base64.b64decode(base64_content)
                                logger.info(
                                    f"Decoded content length: {len(file_content)} bytes"
                                )

                                # Determine MIME type based on file extension or provided type
                                file_type = attachment_info.get(
                                    "type", "application/octet-stream"
                                )
                                main_type, sub_type = (
                                    file_type.split("/", 1)
                                    if "/" in file_type
                                    else ("application", "octet-stream")
                                )

                                # Create MIME part with proper type
                                part = MIMEBase(main_type, sub_type)
                                part.set_payload(file_content)

                                # Encode the payload
                                encoders.encode_base64(part)

                                # Add header
                                part.add_header(
                                    "Content-Disposition",
                                    f'attachment; filename="{filename}"',
                                )

                                # Attach to message
                                message.attach(part)
                                logger.info(
                                    f"Successfully attached: {filename} ({len(file_content)} bytes)"
                                )

                            except Exception as e:
                                logger.error(
                                    f"Error processing attachment {filename}: {str(e)}"
                                )
                                import traceback

                                logger.error(traceback.format_exc())
                        else:
                            logger.warning(
                                f"No content found for attachment: {filename}"
                            )

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            # Send message
            if not self.service:
                await self._initialize_service()

            send_result = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )

            result = {
                "success": True,
                "message_id": send_result["id"],
                "thread_id": send_result["threadId"],
                "status": "sent",
                "to": to,
                "subject": subject,
            }

            logger.info(f"Email sent successfully to {to}")

            return result

        except HttpError as error:
            error_result = {
                "success": False,
                "error": str(error),
                "status": "failed",
                "to": to,
                "subject": subject,
            }
            logger.error(f"Failed to send email: {error}")
            return error_result

    async def get_messages(
        self, query: str = "", max_results: int = 10, include_spam_trash: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve emails from Gmail

        Args:
            query: Gmail search query
            max_results: Maximum number of messages to retrieve
            include_spam_trash: Include spam and trash messages
            access_token: Optional access token for this operation
        Returns:
            List of message dictionaries
        """
        # Ensure authentication
        await self.get_gmail_tokens()
        if not self._validate_gmail_token():
            logger.error("Failed to authenticate with Gmail API")
            return []
        try:
            # Get message list
            if not self.service:
                self._initialize_service()
            results = (
                self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=max_results,
                    includeSpamTrash=include_spam_trash,
                )
                .execute()
            )

            messages = results.get("messages", [])

            if not messages:
                logger.info("No messages found")
                return []

            detailed_messages = []

            # Get details for each message
            if not self.service:
                await self._initialize_service()

            for message in messages:
                msg_detail = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=message["id"], format="full")
                    .execute()
                )

                # Extract message information
                headers = msg_detail["payload"].get("headers", [])
                header_dict = {h["name"].lower(): h["value"] for h in headers}

                # Helper function to get header value with fallbacks
                def get_header_value(header_names):
                    for name in header_names:
                        value = header_dict.get(name.lower())
                        if value:
                            return value
                    return ""

                # Get message body
                body = self._extract_message_body(msg_detail["payload"])

                # Extract recipients more comprehensively
                to_recipients = get_header_value(
                    ["to", "delivered-to", "x-original-to"]
                )
                cc_recipients = get_header_value(["cc"])
                bcc_recipients = get_header_value(["bcc"])

                # Sometimes the recipient info is in the 'delivered-to' or other headers
                if not to_recipients:
                    # Try to get from other possible headers
                    for header in headers:
                        name = header["name"].lower()
                        if "to" in name or "recipient" in name:
                            to_recipients = header["value"]
                            break

                message_info = {
                    "id": msg_detail["id"],
                    "thread_id": msg_detail["threadId"],
                    "labels": msg_detail.get("labelIds", []),
                    "date": get_header_value(["date"]),
                    "from": get_header_value(["from", "sender"]),
                    "to": to_recipients,
                    "cc": cc_recipients,
                    "bcc": bcc_recipients,
                    "subject": get_header_value(["subject"]),
                    "body": body,
                    "is_unread": "UNREAD" in msg_detail.get("labelIds", []),
                }

                detailed_messages.append(message_info)

            logger.info(f"Retrieved {len(detailed_messages)} messages")
            return detailed_messages

        except HttpError as error:
            logger.info(f"Failed to retrieve messages: {error}")
            return []

    def _extract_message_body(self, payload: Dict) -> str:
        """Extract text body from message payload"""
        body = ""

        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    if "data" in part["body"]:
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                            "utf-8"
                        )
                        break
        elif payload["mimeType"] == "text/plain":
            if "data" in payload["body"]:
                body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

        return body

    async def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read"""
        await self.get_gmail_tokens()
        if not self._validate_gmail_token():
            logger.error("Failed to authenticate with Gmail API")
            return False
        if not message_id:
            logger.error("Message ID is required to mark as read")
            return False
        try:
            if not self.service:
                await self._initialize_service()

            self.service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            logger.info(f"Message {message_id} marked as read")
            return True
        except HttpError as error:
            logger.error(f"Failed to mark message as read: {error}")
            return False

    async def delete_message(self, message_id: str) -> bool:
        """Delete a message"""
        await self.get_gmail_tokens()
        if not self._validate_gmail_token():
            logger.error("Failed to authenticate with Gmail API")
            return False
        if not message_id:
            logger.error("Message ID is required to delete a message")
            return False
        try:
            if not self.service:
                await self._initialize_service()

            self.service.users().messages().delete(userId="me", id=message_id).execute()
            logger.info(f"Message {message_id} deleted")
            return True
        except HttpError as error:
            logger.error(f"Failed to delete message: {error}")
            return False

    async def search_emails(
        self, search_criteria: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Advanced email search with multiple criteria

        Args:
            search_criteria: Dictionary with search parameters
                - from: sender email
                - to: recipient email
                - subject: subject contains text
                - has_attachment: boolean
                - is_unread: boolean
                - label: Gmail label
                - newer_than: time period (e.g., '1d', '2w')
                - older_than: time period
                - custom_query: raw Gmail query
                - max_results: number of results
        Returns:
            List of matching messages
        """

        await self.get_gmail_tokens()
        if not self._validate_gmail_token():
            logger.error("Failed to authenticate with Gmail API")
            return []
        if not search_criteria:
            logger.warning("No search criteria provided")
            return []
        # Build Gmail query from search criteria
        query_parts = []

        if search_criteria.get("from"):
            query_parts.append(f"from:{search_criteria['from']}")

        if search_criteria.get("to"):
            query_parts.append(f"to:{search_criteria['to']}")

        if search_criteria.get("subject"):
            query_parts.append(f"subject:{search_criteria['subject']}")

        if search_criteria.get("has_attachment"):
            query_parts.append("has:attachment")

        if search_criteria.get("is_unread"):
            query_parts.append("is:unread")

        if search_criteria.get("label"):
            query_parts.append(f"label:{search_criteria['label']}")

        if search_criteria.get("newer_than"):
            query_parts.append(f"newer_than:{search_criteria['newer_than']}")

        if search_criteria.get("older_than"):
            query_parts.append(f"older_than:{search_criteria['older_than']}")

        if search_criteria.get("custom_query"):
            query_parts.append(search_criteria["custom_query"])

        query = " ".join(query_parts) if query_parts else ""
        max_results = search_criteria.get("max_results", 10)

        return await self.get_messages(query=query, max_results=max_results)

    async def reply_to_email(
        self, original_email: Dict[str, Any], reply_body: str
    ) -> Dict[str, Any]:
        """
        Reply to an email

        Args:
            original_email: Original email dictionary (from get_messages)
            reply_body: Reply message body

        Returns:
            Send result dictionary
        """
        # Extract reply information
        original_from = original_email.get("from", "")
        original_subject = original_email.get("subject", "")

        # Add "Re:" if not present
        reply_subject = original_subject
        if not reply_subject.startswith("Re:"):
            reply_subject = f"Re: {reply_subject}"

        # Send reply
        return await self.send_email(
            to=original_from,
            subject=reply_subject,
            body=reply_body,
        )

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        *,
        timezone: str = "UTC",
        description: str | None = None,
        location: str | None = None,
        attendees: List[str] | None = None,
        reminders_popup_min: int | None = 10,
        calendar_id: str = "primary",
        send_updates: str = "all",
    ) -> Dict[str, Any]:
        """
        Create a Calendar event and (optionally) email invites.
        """
        # make sure creds are valid & services ready
        await self.get_gmail_tokens()
        if not getattr(self, "calendar_service", None):
            await self._initialize_service()

        # Build event body
        event: Dict[str, Any] = {
            "summary": summary,
            "description": description or "",
            "location": location or "",
            "start": {"dateTime": start.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": timezone},
            "attendees": [{"email": a} for a in attendees or []],
        }

        if reminders_popup_min is not None:
            event["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": reminders_popup_min},
                    {"method": "email", "minutes": reminders_popup_min},
                ],
            }

        try:
            result = (
                self.calendar_service.events()
                .insert(
                    calendarId=calendar_id,
                    body=event,
                    sendUpdates=send_updates,  # mails the guests
                )
                .execute()
            )
            return {
                "success": True,
                "event_id": result["id"],
                "htmlLink": result.get("htmlLink"),
                "start": result["start"],
                "end": result["end"],
            }
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return {"success": False, "error": str(e)}

    async def list_calendar_events(
        self,
        *,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary",
        q: Optional[str] = None,
        attendee: Optional[str] = None,
        max_results: int = 10,
        single_events: bool = True,  # expand recurring instances
        order_by: str = "startTime",
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        """
        Return events whose **start or end** occurs between time_min and time_max.
        Additional client-side filtering (free-text or attendee) is optional.
        """

        if max_results > 100:
            raise AppException(ErrorKey.TOO_MANY_RESULTS)
        # 1. make sure creds are valid
        await self.get_gmail_tokens()
        if not getattr(self, "calendar_service", None):
            await self._initialize_service()

        events_call = self.calendar_service.events().list(
            calendarId=calendar_id,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            q=q or None,
            maxResults=max_results,
            singleEvents=single_events,
            orderBy=order_by,
        )

        try:
            items = events_call.execute().get("items", [])
        except Exception as e:
            logger.error(f"Failed to list events: {e}")
            return {"success": False, "error": str(e)}

        # 2. optional: filter by attendee e-mail on the client side
        if attendee:
            attendee_lower = attendee.lower()
            items = [
                e
                for e in items
                if any(
                    a["email"].lower() == attendee_lower for a in e.get("attendees", [])
                )
            ]

        return items
