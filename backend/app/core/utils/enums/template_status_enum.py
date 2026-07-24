import enum


class TemplateStatus(str, enum.Enum):
    """Lifecycle status of a marketplace template.

    ``PRIVATE`` rows live in a tenant DB (the owner's own template). The
    ``PENDING``/``APPROVED``/``REJECTED`` states apply to published copies in the
    master (control-plane) DB; only ``APPROVED`` ones are installable cross-tenant.
    """

    PRIVATE = "private"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
