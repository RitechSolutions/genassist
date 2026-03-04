"""
ConversationRAGIndexer

Lazily indexes conversation message groups into a per-thread vector store
and retrieves semantically relevant groups for LLM context assembly.

Indexing unit: a "group" of consecutive messages (always even count, i.e.
full user+assistant pairs) with configurable overlap between consecutive
groups to avoid semantic context loss at group boundaries.

Sliding-window formula:
    step        = group_size - group_overlap   (must be >= 1)
    group g     covers messages [g*step, g*step + group_size)
    new groups  are detected via rag_indexed_count high-water mark in memory
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.modules.workflow.agents.rag import ThreadScopedRAG


logger = logging.getLogger(__name__)


class ConversationRAGIndexer:
    """
    Manages overlapping message group indexing and contextual retrieval
    for the rag_retrieval memory mode.
    """

    def __init__(
        self,
        thread_rag: ThreadScopedRAG,
        group_size: int = 4,
        group_overlap: int = 2,
        top_k: int = 3,
        query_context_messages: int = 3,
        passthrough_threshold: int = 30,
        recent_messages: int = 6,
        max_history_hours: int = 0,
    ):
        """
        Args:
            thread_rag: ThreadScopedRAG instance for vector store access.
            group_size: Number of messages per indexed group. Must be a
                positive even integer (each pair = 1 user+assistant exchange).
            group_overlap: Number of messages shared between consecutive
                groups. Must satisfy 0 <= group_overlap < group_size.
            top_k: Maximum number of groups to retrieve from the vector store.
            query_context_messages: Number of recent messages combined with
                the current user message to form the retrieval query.
            passthrough_threshold: Total message count below which all messages
                are passed through verbatim without any vector operations.
            recent_messages: Number of most-recent messages always included
                verbatim in context alongside retrieved groups.
            max_history_hours: Exclude retrieved groups whose latest message is
                older than this many hours. 0 disables the filter (no age limit).
        """
        if group_size < 2 or group_size % 2 != 0:
            raise ValueError("group_size must be a positive even integer (>= 2)")
        if group_overlap < 0 or group_overlap >= group_size:
            raise ValueError(
                f"group_overlap must satisfy 0 <= group_overlap < group_size "
                f"(got group_overlap={group_overlap}, group_size={group_size})"
            )

        self.thread_rag = thread_rag
        self.group_size = group_size
        self.group_overlap = group_overlap
        self.top_k = top_k
        self.query_context_messages = query_context_messages
        self.passthrough_threshold = passthrough_threshold
        self.recent_messages = recent_messages
        self.max_history_hours = max_history_hours
        self._step = group_size - group_overlap  # always >= 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def index_new_groups(self, thread_id: str, memory) -> None:
        """
        Batch-index any message groups not yet stored in the vector DB.

        Uses the rag_indexed_count high-water mark to skip groups that were
        already indexed on a previous request, making this operation safe to
        call on every request (idempotent).

        A group is only indexed when it is *complete* — i.e., group_end <=
        total message count. Trailing incomplete groups are deferred to the
        next turn.
        """
        total = await memory.get_total_message_count()
        indexed_count = await memory.get_rag_indexed_count()

        # Find the first group index we should start checking from.
        # All groups where group_end <= indexed_count are assumed indexed.
        if indexed_count == 0:
            start_group = 0
        else:
            # First group that could possibly be new: the one after the last
            # fully indexed group.  last_indexed_g * step + group_size == indexed_count
            # => last_indexed_g = (indexed_count - group_size) / step
            start_group = max(0, (indexed_count - self.group_size) // self._step)

        new_high_water = indexed_count

        g = start_group
        while True:
            group_start = g * self._step
            group_end = group_start + self.group_size

            if group_end > total:
                # Group is not yet complete; stop
                break

            # Skip groups whose end is within the already-indexed range
            if group_end <= indexed_count:
                g += 1
                continue

            messages = await memory.get_messages_by_range(group_start, group_end)
            if not messages:
                g += 1
                continue

            doc_id = self._group_doc_id(thread_id, group_start, group_end)
            group_text = self._format_group_as_text(messages, group_start, group_end)

            timestamps = [m["timestamp"] for m in messages if m.get("timestamp")]
            extra_metadata = {
                "group_start": group_start,
                "group_end": group_end,
                "earliest_timestamp": min(timestamps) if timestamps else None,
                "latest_timestamp": max(timestamps) if timestamps else None,
            }

            await self.thread_rag.add_message(
                chat_id=thread_id,
                message=group_text,
                message_id=doc_id,
                extra_metadata=extra_metadata,
            )
            logger.debug(
                f"[ConversationRAGIndexer] Indexed group [{group_start}:{group_end})"
                f" as doc {doc_id} for thread {thread_id}"
            )

            new_high_water = max(new_high_water, group_end)
            g += 1

        if new_high_water > indexed_count:
            await memory.set_rag_indexed_count(new_high_water)
            logger.debug(
                f"[ConversationRAGIndexer] Updated rag_indexed_count to "
                f"{new_high_water} for thread {thread_id}"
            )

    async def assemble_context(
        self,
        thread_id: str,
        memory,
        current_user_message: str,
    ) -> List[Dict[str, Any]]:
        """
        Full pipeline for assembling LLM context in rag_retrieval mode.

        Steps:
          1. Passthrough check: if total <= passthrough_threshold, return all
             messages verbatim (no vector operations).
          2. Lazy indexing: index any new complete groups.
          3. Build recent verbatim tail (last `recent_messages` messages).
          4. Build contextual retrieval query.
          5. Retrieve relevant historical groups from the vector store.
          6. Deduplicate retrieved content against the recent verbatim window.
          7. Assemble final context list:
               [synthetic system msg with retrieved history]  (if any)
               + [recent verbatim messages]

        Returns:
            Ordered list of message dicts. The same format as other memory
            modes — consumed by create_conversation_context() in agent_prompts.py.
        """
        total = await memory.get_total_message_count()

        # Step 1: passthrough — below threshold, skip RAG entirely
        if total <= self.passthrough_threshold:
            return await memory.get_messages_by_range(0, total)

        # Step 2: lazy indexing
        try:
            await self.index_new_groups(thread_id, memory)
        except Exception as e:
            logger.error(
                f"[ConversationRAGIndexer] index_new_groups failed for "
                f"thread {thread_id}: {e}"
            )
            # Non-fatal: continue with retrieval against whatever is indexed

        # Step 3: recent verbatim tail
        recent_start = max(0, total - self.recent_messages)
        recent_msgs = await memory.get_messages_by_range(recent_start, total)

        # Step 4: build contextual query
        query = self.build_retrieval_query(recent_msgs, current_user_message)

        # Step 5: retrieve
        try:
            retrieved = await self.thread_rag.retrieve(
                chat_id=thread_id,
                query=query,
                top_k=self.top_k,
            )
        except Exception as e:
            logger.error(
                f"[ConversationRAGIndexer] retrieve failed for thread {thread_id}: {e}"
            )
            retrieved = []

        if not retrieved:
            return recent_msgs

        # Step 6: deduplicate and age-filter retrieved groups.
        # - Age filter: skip groups whose latest_timestamp is older than max_history_hours
        #   (when max_history_hours > 0).
        # - Dedup: skip groups that overlap the verbatim recent window, using
        #   group_end index comparison when available; text check as fallback.
        recent_text = self._format_messages_as_text(recent_msgs)
        cutoff: Optional[datetime] = (
            datetime.now() - timedelta(hours=self.max_history_hours)
            if self.max_history_hours > 0
            else None
        )
        relevant_parts = []
        for result in retrieved:
            content = result.get("content", "").strip()
            if not content:
                continue
            meta = result.get("metadata", {})
            if cutoff is not None:
                latest_ts = meta.get("latest_timestamp")
                if latest_ts:
                    try:
                        if datetime.fromisoformat(latest_ts) < cutoff:
                            continue
                    except ValueError:
                        pass
            group_end_meta = meta.get("group_end")
            # A group "overlaps recent" if any of its messages fall inside the
            # verbatim window [recent_start, total). When group_end metadata is
            # present (docs indexed after the metadata enrichment change) we use
            # an exact index comparison: group_end > recent_start means at least
            # one message in the group is already shown verbatim. For older docs
            # without that metadata we fall back to a text substring check.
            overlaps_recent = (
                group_end_meta > recent_start
                if group_end_meta is not None
                else content in recent_text
            )
            if not overlaps_recent:
                relevant_parts.append(content)

        if not relevant_parts:
            return recent_msgs

        # Step 7: assemble
        retrieved_block = self._format_retrieved_block(relevant_parts)
        context: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": retrieved_block,
                "message_type": "rag_retrieved_history",
            }
        ]
        context.extend(recent_msgs)
        return context

    def build_retrieval_query(
        self,
        recent_messages: List[Dict[str, Any]],
        current_user_message: str,
    ) -> str:
        """
        Build a richer embedding query by combining the N most recent messages
        with the current user message. This captures conversational context
        rather than just the surface text of the latest turn.

        Args:
            recent_messages: Recent messages (dicts with 'role' and 'content').
            current_user_message: The user's current input.

        Returns:
            Combined query string for embedding.
        """
        parts = []
        tail = recent_messages[-self.query_context_messages:]
        for msg in tail:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        parts.append(f"User: {current_user_message}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _group_doc_id(thread_id: str, start: int, end: int) -> str:
        """Stable, deterministic document ID for a group."""
        raw = f"{thread_id}:group:{start}:{end}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def _format_group_as_text(
        messages: List[Dict[str, Any]], start_index: int, end_index: int
    ) -> str:
        """Format a group of messages into a single indexable text block."""
        lines = [f"[Conversation history — messages {start_index} to {end_index - 1}]"]
        for msg in messages:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _format_messages_as_text(messages: List[Dict[str, Any]]) -> str:
        """Format messages as plain text for deduplication checks."""
        return "\n".join(
            f"{m.get('role', '').capitalize()}: {m.get('content', '')}"
            for m in messages
        )

    @staticmethod
    def _format_retrieved_block(parts: List[str]) -> str:
        """Format retrieved groups into a single context block."""
        lines = ["[Relevant Conversation History]"]
        for i, part in enumerate(parts, 1):
            lines.append(f"\n--- Retrieved Segment {i} ---")
            lines.append(part)
        return "\n".join(lines)