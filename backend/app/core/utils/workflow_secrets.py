"""Encrypt/decrypt hidden Chat Input parameter default values in workflow definitions.

A Chat Input parameter marked ``hidden: true`` may carry a ``defaultValue``. That
default is part of the workflow definition persisted in the ``workflows`` table, so
we store it encrypted (Fernet) instead of plaintext. It is decrypted at the point of
use (runtime, in ``ChatInputNode``) and when the workflow is loaded for editing.

Encryption reuses the shared ``encrypt_key`` / ``decrypt_key`` helpers (same
``FERNET_KEY`` that secures datasource credentials, API keys, etc.).
"""

import copy
import logging
from typing import Any, Callable, Iterator, Optional

from app.core.utils.encryption_utils import decrypt_key, encrypt_key

logger = logging.getLogger(__name__)

# Marker prefix so encryption is idempotent and decryption can distinguish
# ciphertext produced here from legacy plaintext defaults.
_ENC_PREFIX = "__ENC__:"


def _encrypt_value(value: str) -> str:
    if value.startswith(_ENC_PREFIX):
        return value  # already encrypted — never double-encrypt
    return _ENC_PREFIX + encrypt_key(value)


def _decrypt_value(value: str) -> str:
    if not value.startswith(_ENC_PREFIX):
        return value  # legacy plaintext (or already decrypted) — leave untouched
    return decrypt_key(value[len(_ENC_PREFIX):])


def _transform_schema_defaults(
    input_schema: Any, transform: Callable[[str], str]
) -> None:
    """Apply *transform* in place to the ``defaultValue`` of every hidden param."""
    if not isinstance(input_schema, dict):
        return
    for field in input_schema.values():
        if not isinstance(field, dict) or not field.get("hidden", False):
            continue
        value = field.get("defaultValue")
        if isinstance(value, str) and value != "":
            field["defaultValue"] = transform(value)


def _iter_chat_input_schemas(nodes: Any) -> Iterator[dict]:
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if isinstance(node, dict) and node.get("type") == "chatInputNode":
            schema = node.get("data", {}).get("inputSchema")
            if isinstance(schema, dict):
                yield schema


def encrypt_hidden_defaults(nodes: Optional[list]) -> Optional[list]:
    """Return a copy of *nodes* with hidden params' ``defaultValue`` encrypted."""
    if not nodes:
        return nodes
    nodes = copy.deepcopy(nodes)
    for schema in _iter_chat_input_schemas(nodes):
        _transform_schema_defaults(schema, _encrypt_value)
    return nodes


def decrypt_hidden_defaults(nodes: Optional[list]) -> Optional[list]:
    """Return a copy of *nodes* with hidden params' ``defaultValue`` decrypted."""
    if not nodes:
        return nodes
    nodes = copy.deepcopy(nodes)
    for schema in _iter_chat_input_schemas(nodes):
        _transform_schema_defaults(schema, _decrypt_value)
    return nodes


def decrypt_hidden_defaults_in_schema(input_schema: Any) -> Any:
    """Return a copy of a single node's ``inputSchema`` with hidden defaults decrypted.

    Used at runtime where only the node's own inputSchema is available (not the
    full nodes list).
    """
    if not isinstance(input_schema, dict):
        return input_schema
    input_schema = copy.deepcopy(input_schema)
    _transform_schema_defaults(input_schema, _decrypt_value)
    return input_schema