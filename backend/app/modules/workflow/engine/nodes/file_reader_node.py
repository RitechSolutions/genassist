"""
File reader node implementation using the BaseNode class.

Reads the content of a file and outputs it as text. The file source is either a
fixed file configured on the node ("upload") or every document the user attaches
in the chat at runtime ("chatAttachment"). Images are ignored in chat mode; they
are handled by the Language Model node.
"""

import logging
from typing import Any, Dict
from uuid import UUID

from app.modules.data.utils.file_extractor import FileTextExtractor
from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class FileReaderNode(BaseNode):
    """Reads a file and outputs its text content."""

    async def process(self, config: Dict[str, Any]) -> Any:
        """
        Extract text from the configured file or from chat-attached documents.

        Args:
            config: Resolved node configuration. `fileSource` selects the mode:
                "upload" (default) reads fileId/fileUrl/fileName; "chatAttachment"
                reads every document the user attached in the chat.

        Returns:
            Extracted text content, or an error dict on failure.
        """
        file_source = config.get("fileSource", "upload")

        if file_source == "chatAttachment":
            return await self._read_chat_documents()

        return await self._read_configured_file(config)

    async def _read_configured_file(self, config: Dict[str, Any]) -> Any:
        """Read the single file configured on the node (fixed-upload mode)."""
        file_id = config.get("fileId")
        file_url = config.get("fileUrl")
        file_name = config.get("fileName", "")

        if not file_id and not file_url:
            logger.warning("FileReaderNode: no fileId or fileUrl configured")
            return {"error": "No file configured for File Reader node"}

        try:
            from app.dependencies.injector import injector
            from app.services.file_manager import FileManagerService

            file_service = injector.get(FileManagerService)

            if file_id:
                file_model, content = await file_service.download_file(UUID(file_id))
                file_name = file_name or file_model.original_filename or file_model.name
            else:
                content = await file_service.get_file_content_from_url(file_url)

            if not content:
                return {"error": "File is empty"}

            extractor = FileTextExtractor()
            text = extractor.extract_from_bytes(file_name or "file.bin", content)

            logger.info(
                "FileReaderNode: extracted %d characters from '%s'",
                len(text),
                file_name,
            )
            return text

        except Exception as e:
            error_msg = f"Error reading file: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    async def _read_chat_documents(self) -> str:
        """Read every document attached in the chat, skipping images."""
        from app.dependencies.injector import injector
        from app.services.file_manager import FileManagerService

        file_service = injector.get(FileManagerService)

        attachments = self.get_state().get_value("attachments", []) or []
        documents = [att for att in attachments if not self._is_image(att)]

        if not documents:
            return "No document was attached in the chat."

        sections = []
        for attachment in documents:
            sections.append(await self._read_attachment(file_service, attachment))

        return "\n\n".join(sections)

    async def _read_attachment(self, file_service, attachment: Dict[str, Any]) -> str:
        """Extract one attached document into a labelled, fail-soft text section."""
        file_id = attachment.get("file_id")
        file_url = attachment.get("file_url") or attachment.get("url")
        file_name = attachment.get("name") or attachment.get("file_name") or ""

        try:
            if file_id:
                file_model, content = await file_service.download_file(UUID(file_id))
                file_name = file_name or file_model.original_filename or file_model.name
            else:
                content = await file_service.get_file_content_from_url(file_url)

            text = ""
            if content:
                extractor = FileTextExtractor()
                text = extractor.extract_from_bytes(file_name or "file.bin", content)

        except Exception as e:
            logger.error(
                f"FileReaderNode: failed to read attachment '{file_name}': {str(e)}",
                exc_info=True,
            )
            text = ""

        label = file_name or "document"
        if not text.strip():
            return f"=== {label} ===\n[Could not extract text from {label}]"

        return f"=== {label} ===\n{text}"

    def _is_image(self, attachment: Dict[str, Any]) -> bool:
        """True when the attachment's mime type is an image."""
        mime = attachment.get("type") or attachment.get("file_mime_type") or ""
        return mime.startswith("image")
