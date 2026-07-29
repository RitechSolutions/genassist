"""HTML to Image node: renders an HTML string to a PNG and hosts it."""

import logging
import os
import tempfile
import uuid
from typing import Any, Dict

from app.core.utils.web_scraping_utils import render_html_to_image
from app.modules.workflow.engine import BaseNode

logger = logging.getLogger(__name__)


def _as_int(value: Any, default: int) -> int:
    # config values may arrive as None/""/str/float after template resolution
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class HtmlToImageNode(BaseNode):
    """Render an HTML string in headless Chromium and return a hosted PNG.

    Always returns a result dict and never raises: BaseNode.execute swallows
    exceptions to None, which would leave downstream nodes with nothing to
    branch on, so render/hosting failures come back as {"success": False, ...}.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        html = self._resolve_html(config)
        if not html:
            return self._error("HTML content is required")

        capture_mode = config.get("captureMode") or "fullPage"
        full_page = capture_mode != "viewport"
        viewport_width = _as_int(config.get("viewportWidth"), 1280)
        viewport_height = _as_int(config.get("viewportHeight"), 720)
        wait_for_ms = _as_int(config.get("waitFor"), 0)

        try:
            image_bytes = await render_html_to_image(
                html,
                full_page=full_page,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                wait_for_ms=wait_for_ms,
            )
        except ValueError as exc:
            # empty HTML and other validation failures surface as ValueError
            return self._error(str(exc))
        except Exception as exc:  # timeouts, Playwright and other unexpected failures
            logger.error("HTML to image node failed: %s", exc)
            return self._error(str(exc))

        image_url, file_id = await self._host_image(image_bytes)
        return {
            "success": True,
            "image": image_url,
            "image_file_id": file_id,
            "error": "",
        }

    def _resolve_html(self, config: Dict[str, Any]) -> str:
        """Resolve the HTML source, preferring upstream input over config.

        Order: (1) upstream output that is a non-empty string; (2) upstream dict
        unwrapped via ``html`` then ``content``; (3) ``config["html"]``.
        """
        source_output = self.get_input_from_source()
        if isinstance(source_output, str) and source_output.strip():
            return source_output
        if isinstance(source_output, dict):
            for key in ("html", "content"):
                value = source_output.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        config_html = config.get("html")
        if isinstance(config_html, str) and config_html.strip():
            return config_html
        return ""

    async def _host_image(self, image_bytes: bytes) -> tuple[str, str]:
        """Return ``(image_url, image_file_id)`` for the rendered PNG; never raises.

        Hosts the PNG via FileManagerService so the output carries a short source URL.
        The public ``/source`` route works regardless of the file-manager flag;
        on any failure the fields stay empty.
        """
        try:
            return await self._host_via_file_manager(image_bytes)
        except Exception as exc:
            logger.warning("Image hosting failed: %s", exc)
            return "", ""

    async def _host_via_file_manager(self, image_bytes: bytes) -> tuple[str, str]:
        """Upload the PNG through FileManagerService, returning ``(url, file_id)``.

        Fetch the "File Manager Settings" row so
        the configured provider (local in dev, S3 in prod) is used; a missing row leaves
        ``app_settings=None`` and initialize falls back to env provider config.
        """
        from app.core.config.settings import file_storage_settings
        from app.core.project_path import DATA_VOLUME
        from app.dependencies.injector import injector
        from app.schemas.file import FileBase
        from app.services.app_settings import AppSettingsService
        from app.services.file_manager import FileManagerService

        fm = injector.get(FileManagerService)
        app_cfg = await injector.get(AppSettingsService).get_by_type_and_name(
            "FileManagerSettings", "File Manager Settings"
        )
        # base_url is mandatory for the local provider's source URL; nodes have no request
        provider = await fm.initialize(
            base_url=(file_storage_settings.APP_URL or "http://localhost:8000").rstrip("/"),
            base_path=str(DATA_VOLUME),
            app_settings=app_cfg,
        )

        name = f"{uuid.uuid4()}.png"
        tmp = os.path.join(tempfile.gettempdir(), name)
        with open(tmp, "wb") as handle:
            handle.write(image_bytes)

        file_base = FileBase(
            name=name,
            storage_path=provider.get_base_path(),
            path="html_to_image_screenshots",
            storage_provider=provider.name,
            file_extension="png",
        )
        created = await fm.create_file_from_local_path(
            tmp,
            file_base=file_base,
            original_filename=name,
            mime_type="image/png",
            delete_source=True,
        )
        # local -> /api/file-manager/.../source ; s3 -> presigned URL
        return await fm.get_file_url(created), str(created.id)

    @staticmethod
    def _error(message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "image": "",
            "image_file_id": "",
            "error": message,
        }
