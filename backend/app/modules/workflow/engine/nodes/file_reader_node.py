"""
File reader node implementation using the BaseNode class.

Reads the content of an uploaded file and outputs it as text.
"""

import logging
from typing import Any, Dict

from app.modules.data.utils.file_extractor import FileTextExtractor
from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class FileReaderNode(BaseNode):
    """Reads an uploaded file and outputs its text content."""

    async def process(self, config: Dict[str, Any]) -> Any:
        """
        Download the file referenced by fileId or fileUrl and extract its text.

        Args:
            config: Resolved node configuration containing fileId, fileUrl, fileName.

        Returns:
            Extracted text content of the file, or an error dict on failure.
        """
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
                from uuid import UUID
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
