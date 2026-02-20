"""
Memory compaction service for conversation history management.

This service uses an LLM to compact older conversation messages into:
1. Entity/fact store (structured JSON)
2. Prose summary (natural language narrative)
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
import json
import re
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage


logger = logging.getLogger(__name__)


class MemoryCompactor:
    """Handles compaction of conversation history into summaries and entity stores"""

    # Prompt template for LLM-based compaction
    COMPACTION_PROMPT = """Your task is to analyze a conversation history and extract:

1. Key entities and facts (structured data)
2. A flowing prose summary that captures the conversation's context and nuances

You will receive a series of messages from a conversation{previous_compaction_prompt}. Create a compact representation that preserves:
- Important facts, entities, and their relationships
- Context and conversation flow
- User preferences and stated goals
- Key decisions or conclusions

{previous_expansion_prompt}

Respond with a JSON object in this exact format:
{{
  "entities": [
    {{"type": "person", "name": "...", "attributes": {{}}}},
    {{"type": "fact", "description": "...", "context": "..."}},
    {{"type": "preference", "description": "...", "stated_by": "user"}},
    ...
  ],
  "prose_summary": "A flowing narrative summary that maintains conversation context and nuance. This should read naturally and help the AI understand the conversation history..."
}}

Conversation history to compact:
{conversation_history}

Provide the JSON response:"""

    def __init__(self, llm_model: BaseChatModel):
        """
        Initialize memory compactor.

        Args:
            llm_model: LLM to use for compaction
        """
        self.llm_model = llm_model

    async def compact_messages(
        self,
        messages: List[Dict[str, Any]],
        existing_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compact a list of messages into entity store and prose summary.

        Args:
            messages: List of message dicts with 'role' and 'content'
            existing_summary: Previous compacted summary to merge with (if any)

        Returns:
            Dictionary with:
            - entities: List of extracted entities/facts
            - prose_summary: Natural language summary
            - compacted_message_count: Number of messages compacted
            - compacted_until_timestamp: Timestamp of last compacted message
            - last_compaction_timestamp: When this compaction was performed
        """
        if not messages:
            return existing_summary if existing_summary else self._empty_summary()

        # Format conversation history for LLM
        history_text = self._format_messages_for_compaction(messages, existing_summary)

        # Call LLM to generate compacted representation
        try:
            # add existing summary explanation to the prompt if it exists, otherwise just pass messages
            prompt = self.COMPACTION_PROMPT.format(conversation_history=history_text,
                                                   previous_compaction_prompt=" and previous summary done for "
                                                                              "messages before the latest ones "
                                                                              "included "
                                                                              "below" if existing_summary else "",
                                                   previous_expansion_prompt="Expand or update the previous "
                                                                             "compaction summary with "
                                                                             "new data as necessary, while loosing "
                                                                             "the least amount of previous context." if
                                                   existing_summary else "")

            response = await self.llm_model.ainvoke([
                SystemMessage(content="You are a helpful assistant that compacts conversation history."),
                HumanMessage(content=prompt)
            ])

            # Parse LLM response (expecting JSON)
            result = self._parse_llm_response(response.content)

            # Add metadata
            result["compacted_message_count"] = len(messages) + existing_summary.get("compacted_message_count", 0) if existing_summary else len(messages)
            result["compacted_until_timestamp"] = messages[-1].get("timestamp", datetime.now().isoformat())
            result["last_compaction_timestamp"] = datetime.now().isoformat()

            logger.info(f"Compacted {len(messages)} messages into summary with {len(result.get('entities', []))} entities")

            return result

        except Exception as e:
            logger.error(f"Error during message compaction: {e}")
            # Return existing summary or empty on error
            return existing_summary if existing_summary else self._empty_summary()

    def _format_messages_for_compaction(
        self,
        messages: List[Dict[str, Any]],
        existing_summary: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format messages and existing summary for LLM prompt"""
        parts = []

        # Include existing summary context if available
        if existing_summary:
            parts.append("=== Previous Summary ===")
            if existing_summary.get("prose_summary"):
                parts.append(f"Context: {existing_summary['prose_summary']}")
            if existing_summary.get("entities"):
                parts.append(f"Known entities: {len(existing_summary['entities'])} items")
            parts.append("\n=== New Messages to Compact ===")

        # Format messages
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")
            parts.append(f"[{timestamp}] {role.capitalize()}: {content}")

        return "\n".join(parts)

    def _parse_llm_response(self, response_content: str) -> Dict[str, Any]:
        """Parse LLM response, extracting JSON even if wrapped in markdown"""
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("No JSON found in LLM response")

        parsed = json.loads(json_str)

        # Validate structure
        if "entities" not in parsed or "prose_summary" not in parsed:
            raise ValueError("Invalid compaction response format")

        return parsed

    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure"""
        return {
            "entities": [],
            "prose_summary": "",
            "compacted_message_count": 0,
            "compacted_until_timestamp": None,
            "last_compaction_timestamp": None
        }