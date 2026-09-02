from enum import Enum


class ReaderRole(str, Enum):
    """Who a read receipt belongs to.

    A conversation has at most two human readers: the visitor (``CUSTOMER``) on the
    embedded chat widget, and the human ``SUPERVISOR`` on the agent console after a
    takeover. The AI agent is never a reader — it consumes every message
    deterministically, so an AI "seen" carries no signal.
    """

    CUSTOMER = "customer"
    SUPERVISOR = "supervisor"
