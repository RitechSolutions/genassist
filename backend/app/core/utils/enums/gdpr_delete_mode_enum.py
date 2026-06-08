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
      (cascades to ``transcript_messages`` and ``conversation_analysis``) and
      supporting stores (Redis memory, RAG, recordings, audit snapshots).
      Already-aggregated daily analytics counts are unaffected.
    """

    SOFT = "soft"
    ANONYMIZE = "anonymize"
    HARD = "hard"
