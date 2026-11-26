"""Images a chat turn carries, as content blocks for the model's user message.

Shared by the LLM Model node and every agent type, so a workflow sees the visitor's
image whichever node answers. Documents are not handled here (the File Reader node
reads those).
"""

import base64
from typing import Any, Dict, List, Optional, Union

# Stands in for the user's text when they sent only an image: some providers reject an
# empty text block, and an empty prompt reads to the model as "nothing was sent".
IMAGE_ONLY_PROMPT = "The user sent the attached image without any text."


def _mime_type(attachment: Dict[str, Any]) -> str:
    return attachment.get("type") or attachment.get("file_mime_type") or ""


def image_content_blocks(attachments: Optional[List[Any]]) -> List[Dict[str, Any]]:
    """``image_url`` content blocks for the image attachments; other files are skipped.

    A file on the server's own disk is inlined as a data URL. Only attachments the
    server resolved itself (``file_storage_provider`` is set while the turn processes
    attachments and stripped from what the browser sends) are read from disk, so a
    visitor cannot make the server read a path of their choosing. Raises ``OSError``
    when such a file cannot be read.
    """
    blocks: List[Dict[str, Any]] = []
    for attachment in attachments or []:
        if not isinstance(attachment, dict) or not _mime_type(attachment).startswith("image"):
            continue

        url = attachment.get("file_url") or attachment.get("url")
        local_path = attachment.get("file_local_path") if attachment.get("file_storage_provider") == "local" else None
        if local_path:
            with open(local_path, "rb") as image_file:
                encoded = base64.standard_b64encode(image_file.read()).decode("utf-8")
            mime_type = attachment.get("file_mime_type") or _mime_type(attachment)
            url = f"data:{mime_type};base64,{encoded}"

        if url:
            blocks.append({"type": "image_url", "image_url": {"url": url}})
    return blocks


def with_images(text: str, images: Optional[List[Dict[str, Any]]]) -> Union[str, List[Dict[str, Any]]]:
    """A user message's content: the plain text, or a text block followed by the images."""
    if not images:
        return text
    return [{"type": "text", "text": text if (text or "").strip() else IMAGE_ONLY_PROMPT}, *images]
