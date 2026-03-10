"""
LLM Analyst context enrichment registry.

Each enrichment represents an optional piece of per-conversation data that can
be fetched at analysis time and injected into the prompt. Frontend reads this
list to populate the enrichment selector in the LLM Analyst form.
"""

from typing import TypedDict, List


class EnrichmentSchema(TypedDict):
    key: str
    name: str
    description: str


AVAILABLE_ENRICHMENTS: List[EnrichmentSchema] = [
    {
        "key": "zendesk_ticket_created",
        "name": "Zendesk Ticket Status",
        "description": (
            "Whether a Zendesk ticket was opened during the conversation. "
            "Use this to inform scoring, e.g. Resolution Rate: 10 if no ticket created, 0 if ticket was created."
        ),
    },
    {
        "key": "knowledge_base_used",
        "name": "Knowledge Base Usage",
        "description": (
            "Whether the agent queried a knowledge base during the conversation. "
            "Use this to assess Operator Knowledge: a higher score may be warranted when the agent leveraged available knowledge resources."
        ),
    },
]