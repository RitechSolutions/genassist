"""
Calendar events node implementation using the BaseNode class.
"""
from uuid import UUID
from app.core.exceptions.error_messages import ErrorKey, get_error_message
from app.core.exceptions.exception_classes import AppException
from app.core.utils.encryption_utils import decrypt_key
from app.modules.integration.gmail_connector import GmailConnector
from app.modules.integration.office365_connector import Office365Connector
from app.services.datasources import DataSourceService
from app.services.app_settings import AppSettingsService

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict

from ..base_node import BaseNode


logger = logging.getLogger(__name__)


class CalendarEventsNode(BaseNode):
    """Calendar events node using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates or searches calendar events depending on operation.

        Accepted operations & required keys:
        1. create_calendar_event → summary, start, end, timezone
        2. search_calendar_events → start, end, timezone
           optional: subject_contains, attendee, max_results

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with calendar operation results
        """
        try:
            from app.dependencies.injector import injector

            # Get configuration values (already resolved by BaseNode)
            data_source_id = config.get("dataSourceId")
            operation = config.get("operation", "").lower()
            timezone = config.get("timezone", "UTC")

            # Validate data source ID
            if not data_source_id:
                raise AppException(error_key=ErrorKey.MISSING_DATA_SOURCE_ID)

            # Get data source
            ds_service = injector.get(DataSourceService)
            data_src = await ds_service.get_by_id(data_source_id, decrypt_sensitive=True)

            # Set timezone
            tz = ZoneInfo(timezone)

            if not data_src or not data_src.source_type:
                result = {
                    "result": "Data source type or operation is not supported."}
                return result

            # Handle different data source types
            if data_src and data_src.source_type and data_src.source_type.lower() == "gmail":
                result = await self._handle_gmail_event(data_source_id, config, operation, tz)
            elif data_src and data_src.source_type and data_src.source_type.lower() == "o365":
                result = await self._handle_outlook_event(injector, data_src, config, operation, tz)
            else:
                result = {
                    "result": "Data source type or operation is not supported."}

            return {"result": result}

        except AppException as e:
            error_msg = get_error_message(e.error_key)
            logger.error(
                f"Calendar operation failed with AppException: {error_msg}")
            return {"result": error_msg}
        except Exception as e:
            error_msg = "An error happened while managing the event"
            logger.error(f"Calendar operation failed: {e}")
            return {"result": error_msg}

    def _parse_dt(self, value: str | None, tz: ZoneInfo) -> datetime | None:
        """Parse an ISO date string to a timezone‑aware datetime (or return None)."""
        if value:
            return datetime.fromisoformat(value).replace(tzinfo=tz)
        return None

    def _require(self, node_cfg: dict[str, Any], *keys: str) -> None:
        """Ensure all *keys are present; otherwise raise AppException."""
        missing = [k for k in keys if not node_cfg.get(k)]
        if missing:
            raise AppException(error_key=ErrorKey.MISSING_PARAMETER)

    async def _handle_gmail_event(self, ds_id, node_config, op, tz):
        gmail = GmailConnector(ds_id)

        if op == "create_calendar_event":
            self._require(node_config, "summary", "start",
                          "end")  # <‑‑ validation
            resp = await gmail.create_event(
                summary=node_config["summary"],
                start=self._parse_dt(node_config["start"], tz),
                end=self._parse_dt(node_config["end"], tz),
            )
            return {
                "message": "Event created successfully" if resp.get("success")
                else "Failed to create the event",
                "link": resp.get("htmlLink", "")
            }

        elif op == "search_calendar_events":
            self._require(node_config, "start", "end")
            kwargs = {
                "start": self._parse_dt(node_config.get("start"), tz),
                "end": self._parse_dt(node_config.get("end"), tz),
                "q": node_config.get("subjectContains"),
                "attendee": node_config.get("attendee"),
                "max_results": node_config.get("max_results", 10),
            }
            # Drop keys whose value is None so Gmail API isn’t called with them
            events = await gmail.list_calendar_events(**{k: v for k, v in kwargs.items() if v is not None})
            return {"events": events}

        return {"message": "Operation type not supported"}

    async def _handle_outlook_event(self, injector, data_src, node_config, op, tz):
        # Get app_settings_id from data source connection_data
        app_settings_id = data_src.connection_data.get("app_settings_id")
        if not app_settings_id:
            raise Exception("App settings ID not found in data source")

        # Get app settings by ID
        settings = injector.get(AppSettingsService)
        app_settings = await settings.get_by_id(UUID(app_settings_id))

        # Extract values from the values field
        values = app_settings.values if isinstance(
            app_settings.values, dict) else {}
        client_id = values.get("microsoft_client_id")
        client_secret = values.get("microsoft_client_secret")
        tenant_id = values.get("microsoft_tenant_id")

        # Decrypt client_secret
        if client_secret:
            client_secret = decrypt_key(client_secret)

        if not client_id or not client_secret or not tenant_id:
            raise Exception("Microsoft credentials not found in app settings!")

        o365_client = Office365Connector(
            for_sharepoint=False,
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            refresh_token=data_src.connection_data["refresh_token"],
            redirect_uri=data_src.connection_data["redirect_uri"],
        )

        if op == "create_calendar_event":
            self._require(node_config, "summary", "start", "end")
            resp = await o365_client.create_calendar_event(
                summary=node_config["summary"],
                start=self._parse_dt(node_config["start"], tz),
                end=self._parse_dt(node_config["end"], tz),
            )
            return {
                "message": "Event created successfully",
                "link": resp.get("webLink", "")
            }

        elif op == "search_calendar_events":
            self._require(node_config, "start", "end")
            kwargs = {
                "start": self._parse_dt(node_config.get("start"), tz),
                "end": self._parse_dt(node_config.get("end"), tz),
                "subject_contains": node_config.get("subjectContains"),
                "attendee": node_config.get("attendee"),
                "top": node_config.get("max_results", 100),
                "timezone": node_config.get("timezone", "UTC"),
            }
            events = await o365_client.list_calendar_events(
                **{k: v for k, v in kwargs.items() if v is not None}
            )
            return {"events": events}

        return {"message": "Operation type not supported"}
