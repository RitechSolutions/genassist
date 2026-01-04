import uuid


def get_customer_id(identifier: str) -> str:
    """Deterministically generate customer_id from any channel/phone ID."""
    FIXED_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid.uuid5(FIXED_NAMESPACE, identifier))
