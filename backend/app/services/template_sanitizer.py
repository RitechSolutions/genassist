"""Sanitize & validate workflow graphs for the Template Marketplace.

GenAssist is database-per-tenant, so a template's node graph must never carry
values that only make sense in the source tenant:

* **Per-tenant references** (LLM provider / knowledge base / datasource / audio
  provider IDs) point at rows in another tenant's database and are blanked, so
  the installing user re-selects their own via the Setup Wizard.
* **Secrets** (inline auth tokens, MCP connection config, encrypted hidden
  Chat-Input defaults) must never travel inside a template and are stripped.

These helpers run when a template is saved (so stored graphs are always clean)
and again defensively on install.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, List, Optional, Tuple

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

logger = logging.getLogger(__name__)

# node.data fields that reference rows in the *source* tenant's DB.
PER_TENANT_REF_FIELDS = (
    "providerId",
    "selectedBases",
    "audioProviderId",
    "voiceProviderId",
    "dataSourceId",
)

# node.data fields that may hold plaintext secrets — must never live in a template.
# ``headers`` is a free-form JSON-object field (e.g. on webScraperNode) that
# commonly carries Authorization tokens, cookies, or API keys.
SECRET_DATA_FIELDS = (
    "authToken",
    "authPassword",
    "authUsername",
    "authHeader",
    "connectionConfig",
    "headers",
)


def _blank(value: Any) -> Any:
    if isinstance(value, list):
        return []
    if isinstance(value, dict):
        return {}
    return None


def sanitize_graph(
    nodes: Optional[List[dict]],
    edges: Optional[List[dict]],
) -> Tuple[List[dict], List[dict]]:
    """Return a deep-copied (nodes, edges) safe to store and share across tenants."""
    safe_nodes: List[dict] = copy.deepcopy(nodes or [])
    safe_edges: List[dict] = copy.deepcopy(edges or [])

    for node in safe_nodes:
        data = node.get("data") if isinstance(node, dict) else None
        if not isinstance(data, dict):
            continue

        # 1. Blank per-tenant references (forces re-selection via the Setup Wizard).
        for field in PER_TENANT_REF_FIELDS:
            if field in data:
                data[field] = _blank(data[field])

        # 2. Strip inline secrets.
        for field in SECRET_DATA_FIELDS:
            data.pop(field, None)

        # 3. Strip hidden Chat-Input default values (encrypted secrets on read).
        input_schema = data.get("inputSchema")
        if isinstance(input_schema, dict):
            for field_schema in input_schema.values():
                if isinstance(field_schema, dict) and field_schema.get("hidden"):
                    field_schema.pop("defaultValue", None)

    return safe_nodes, safe_edges


def _valid_node_types() -> set[str]:
    # Lazy import: routes import services, so importing the workflows route at
    # module load could create a cycle. By install time everything is loaded.
    from app.api.v1.routes.workflows import SUPPORTED_NODE_TYPES

    return set(SUPPORTED_NODE_TYPES)


def validate_node_types(nodes: Optional[List[dict]]) -> None:
    """Raise AppException(400) if the graph uses any unsupported node type."""
    valid = _valid_node_types()
    unknown = sorted(
        {
            n.get("type")
            for n in (nodes or [])
            if isinstance(n, dict) and n.get("type") not in valid
        }
        - {None}
    )
    if unknown:
        raise AppException(
            error_key=ErrorKey.TEMPLATE_INVALID,
            status_code=400,
            error_detail=f"Template uses unsupported node types: {', '.join(unknown)}",
        )
