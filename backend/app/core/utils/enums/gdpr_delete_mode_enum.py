from enum import Enum


class GdprDeleteMode(str, Enum):
    """Modes supported by the admin GDPR conversation deletion endpoint.

    - ``SOFT``: flip the existing ``is_deleted`` flag and scrub
      ``custom_attributes.pii``. File Manager blobs are not removed so the
      row can be reconciled without losing uploads. The row is hidden from
      standard reads by the global soft-delete ORM filter. Default mode.
    - ``ANONYMIZE``: keep the row visible (analytics drilldowns continue to
      work), but scrub ``custom_attributes.pii``, purge File Manager objects
      referenced by the transcript (and related fields), replace ``type=file``
      payloads with placeholders, and run ``redact_sensitive_substrings`` on
      other message text. Stamps ``conversations.pii_redacted_at`` for auditing.
    - ``HARD``: purge File Manager attachments, then remove the conversation row
      (cascades to ``transcript_messages``, ``conversation_analysis`` and
      ``agent_response_logs``) and supporting stores (Redis memory, RAG,
      recordings, audit snapshots). Daily analytics are rebuilt from the
      remaining logs: with ``ANALYTICS_AGG_V2`` on, the conversation drops out
      of today's and yesterday's counts on the next scheduled runs, and out of
      older dates whenever those are backfilled. Legacy aggregation only
      revisits a date that receives new logs, so older counts usually keep it.
    """

    SOFT = "soft"
    ANONYMIZE = "anonymize"
    HARD = "hard"
