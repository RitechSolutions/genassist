from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.utils.enums.template_status_enum import TemplateStatus
from app.db.base import Base


class TemplateModel(Base):
    """A reusable agent/workflow template for the Template Marketplace.

    The same model backs two physically separate stores (schema is shared across
    the master and every tenant DB):

    * **Tenant DB** — a user's private template (``status="private"``,
      ``created_by`` = owner). Never leaves that tenant.
    * **Master (control-plane) DB** — a *published* copy submitted for global
      sharing (``status`` in ``pending``/``approved``/``rejected``). Only rows
      here are visible cross-tenant, and only ``approved`` ones are installable.
      Global rows are always accessed via the ``"master"`` session factory.

    ``graph`` is an already-sanitized workflow graph (secrets stripped, per-tenant
    references blanked). See ``app.services.template_sanitizer``.
    """

    __tablename__ = "templates"

    title = Column(String(120), nullable=False)
    description = Column(String(500), nullable=True)
    category = Column(String(60), nullable=True)
    # Lucide icon name (e.g. "Headphones") or emoji, used by the gallery card.
    icon = Column(String(60), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    # Distinct node types present in the graph, for preview chips + validation.
    node_types: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    # Sanitized workflow graph: {"nodes": [...], "edges": [...], "testInput": {...}?}
    graph: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Default agent config applied on install (name/description/welcome_message/...).
    agent_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_official = Column(Boolean, nullable=False, server_default="false")
    # Number of times this template has been installed (drives "most used").
    install_count = Column(Integer, nullable=False, server_default="0")

    # ---- publishing / approval lifecycle ----
    # private (tenant-local) | pending | approved | rejected — see TemplateStatus.
    # Kept as a plain String column (not sa.Enum) so no DB-level enum type is
    # created; values are constrained in the app layer via TemplateStatus.
    status = Column(String(20), nullable=False, server_default=TemplateStatus.PRIVATE.value)
    # Slug of the tenant a published copy originated from.
    source_tenant = Column(String(120), nullable=True)
    # User who submitted the publish request.
    published_by = Column(PGUUID(as_uuid=True), nullable=True)
    # The originating tenant-local template id (for dedup / traceability).
    source_template_id = Column(PGUUID(as_uuid=True), nullable=True)
    # Master-admin who approved/rejected, and when.
    approved_by = Column(PGUUID(as_uuid=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(500), nullable=True)
