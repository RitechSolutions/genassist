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
            "Appends to the prompt: 'Zendesk ticket created: Yes/No'. "
            "Add instructions in your prompt referencing this, e.g. "
            "'Score Resolution Rate 0 if a Zendesk ticket was created, 10 if not.'"
        ),
    },
    {
        "key": "knowledge_base_used",
        "name": "Knowledge Base Usage",
        "description": (
            "Appends to the prompt: 'Knowledge base queried: Yes/No'. "
            "Add instructions in your prompt referencing this, e.g. "
            "'Score Operator Knowledge higher if the agent queried the knowledge base.'"
        ),
    },
]