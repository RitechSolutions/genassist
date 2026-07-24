"""Bundled catalog of official templates for the Template Marketplace.

Official templates are read-only and shared across all tenants, so — unlike
user-saved templates — they are NOT stored in the database. They are derived at
runtime from the existing seed workflow JSONs (``app/db/seed/*_wf_data.json``),
sanitized, and given a deterministic id so install/get can resolve them.
"""
from __future__ import annotations

import json
import logging
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.exceptions.exception_classes import AppException
from app.services.template_sanitizer import (
    sanitize_graph,
    sanitize_test_input,
    validate_node_types,
)

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).resolve().parent.parent / "db" / "seed"
# Fixed namespace so an official template's id is stable across restarts/tenants.
_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://genassist.ai/templates")

# Bundled official templates are intentionally empty — the library is populated
# entirely by tenant-published, master-approved (community) templates.
_OFFICIAL: List[Dict[str, str]] = []


def _load_template(meta: Dict[str, str]) -> Optional[Dict[str, Any]]:
    path = SEED_DIR / meta["file"]
    if not path.exists():
        logger.warning("Official template file missing: %s", path)
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        # Seed files embed the KB_ID_LIST placeholder (invalid JSON); neutralize
        # it to an empty list — knowledge bases are re-selected on install anyway.
        raw = raw.replace('"KB_ID_LIST"', "[]").replace("KB_ID_LIST", "[]")
        data = json.loads(raw)
    except Exception:
        logger.exception("Failed to parse official template %s", meta["file"])
        return None

    nodes, edges = sanitize_graph(data.get("nodes"), data.get("edges"))
    graph: Dict[str, Any] = {"nodes": nodes, "edges": edges}
    safe_test_input = sanitize_test_input(nodes, data.get("testInput"))
    if safe_test_input is not None:
        graph["testInput"] = safe_test_input

    node_types = sorted(
        {n.get("type") for n in nodes if isinstance(n, dict) and n.get("type")}
    )

    # Never surface an official template that can't be installed. If the graph
    # uses an unsupported node type (e.g. seed/allow-list drift), skip it. Fail
    # open on any other error — install-time validation still guards.
    try:
        validate_node_types(nodes)
    except AppException:
        logger.warning(
            "Skipping official template %s: unsupported node types %s",
            meta["file"],
            node_types,
        )
        return None
    except Exception:
        logger.exception(
            "Could not validate node types for %s; including it anyway", meta["file"]
        )

    description = meta.get("description") or data.get("description") or meta["title"]

    return {
        "id": uuid.uuid5(_NS, meta["slug"]),
        "title": meta["title"],
        "description": description,
        "category": meta.get("category"),
        "icon": meta.get("icon"),
        "tags": [meta["category"]] if meta.get("category") else [],
        "node_types": node_types,
        "node_count": len(nodes),
        "graph": graph,
        "agent_config": {
            "name": meta["title"],
            "description": description[:200],
            "welcome_message": "Hi! How can I help you today?",
            "possible_queries": [],
        },
        "is_official": True,
    }


@lru_cache(maxsize=1)
def get_official_templates() -> List[Dict[str, Any]]:
    templates: List[Dict[str, Any]] = []
    for meta in _OFFICIAL:
        loaded = _load_template(meta)
        if loaded is not None:
            templates.append(loaded)
    return templates


def get_official_template(template_id: Any) -> Optional[Dict[str, Any]]:
    target = str(template_id)
    for tmpl in get_official_templates():
        if str(tmpl["id"]) == target:
            return tmpl
    return None
