from enum import Enum


class GdprDeleteMode(str, Enum):
    """Modes supported by the admin GDPR conversation deletion endpoint.

    - ``SOFT``: flip the existing ``is_deleted`` flag and scrub
      ``custom_attributes.pii``. Reversible while the row is still on disk;
      the row is hidden from all standard reads by the global soft-delete
      ORM filter. Default mode for backward compatibility.
    - ``ANONYMIZE``: keep the row visible (analytics drilldowns continue to
      work), but scrub ``custom_attributes.pii`` and run the existing
      ``redact_sensitive_substrings`` helper over each transcript message
      ``text`` field. Stamps ``conversations.pii_redacted_at`` so the action
      is auditable.
    - ``HARD``: delegate to the existing internal ``delete_conversation``
      path, which removes the conversation row and cascades to
      ``transcript_messages`` and ``conversation_analysis``. Already-aggregated
      daily analytics counts are unaffected.
    """

    SOFT = "soft"
    ANONYMIZE = "anonymize"
    HARD = "hard"
