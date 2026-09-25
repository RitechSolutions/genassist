"""Entry (trigger) node types.

A workflow may carry more than one entry node, e.g. a Chat Input for the chat
channel and a Webhook Trigger for external systems. A run starts from exactly
one of them; the others are *unused entry nodes* for that run and must neither
block downstream requirement checks nor contribute input.
"""

ENTRY_NODE_TYPES = frozenset({"chatInputNode", "webhookTriggerNode"})


def is_entry_node_type(node_type: str | None) -> bool:
    return node_type in ENTRY_NODE_TYPES
