from typing import List

from ..base import FieldSchema

# "End Conversation" node — minimal config. The node always finalizes the run's
# own conversation using the system default analyst (C4), so it exposes only an
# optional display name.
FINALIZE_CONVERSATION_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    )
]
