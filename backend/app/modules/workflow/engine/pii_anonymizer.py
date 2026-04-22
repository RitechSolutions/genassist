from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Realistic fake value generators per entity type.
# These produce values that look natural to an LLM while being clearly fake
# (using reserved/fictional ranges where possible).
_FAKE_VALUE_TEMPLATES: dict[str, Any] = {
    "EMAIL_ADDRESS": lambda n: f"johndoe{n}@example.com",
    "PHONE_NUMBER": lambda n: f"(555) 010-{n:04d}",  # 555 is reserved for fiction
    "CREDIT_CARD": lambda n: f"4111-1111-1111-{n:04d}",
    "IP_ADDRESS": lambda n: f"192.0.2.{n}",  # TEST-NET-1, reserved for docs
    "IBAN_CODE": lambda n: f"DE00000000000000000{n:03d}",
    "US_SSN": lambda n: f"000-00-{n:04d}",
    "US_ITIN": lambda n: f"900-00-{n:04d}",
    "US_PASSPORT": lambda n: f"A{n:08d}",
    "US_DRIVER_LICENSE": lambda n: f"D000-{n:04d}",
    "UK_NHS": lambda n: f"000 000 {n:04d}",
    "MEDICAL_LICENSE": lambda n: f"MED-{n:04d}",
}

# Only entities with built-in regex recognizers in Presidio's default "en"
# registry are listed. Language-specific IDs (IT/ES/PL) and identifiers
# without built-in recognizers (CA_SIN, AU_*, IN_*, SG_*) are excluded —
# they produce no detections without spaCy NER or custom recognizers.
# US_BANK_NUMBER is also excluded: its loose 8-17 digit regex causes false
# positives on phone numbers and other numeric strings.
DEFAULT_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "IBAN_CODE",
    "US_SSN",
    "US_ITIN",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "UK_NHS",
    "MEDICAL_LICENSE",
]


@lru_cache(maxsize=1)
def _get_engines():
    """Lazy-init Presidio analyzer — cached per process, no spaCy model required."""
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngine

    class _PatternOnlyNlpEngine(NlpEngine):
        """Stub NLP engine that satisfies Presidio's interface without loading any model."""

        engine_name = "pattern_only"

        def load(self) -> None:
            pass

        def is_loaded(self) -> bool:
            return True

        def process_text(self, text: str, language: str) -> NlpArtifacts:
            return NlpArtifacts(
                entities=[],
                tokens=[],
                tokens_indices=[],
                lemmas=[],
                nlp_engine=self,
                language=language,
            )

        def process_batch(self, texts, language):  # type: ignore[override]
            return [self.process_text(t, language) for t in texts]

        def get_supported_languages(self) -> list[str]:
            return ["en"]

        def get_supported_entities(self, language: str | None = None) -> list[str]:
            return []

        def is_stopword(self, word: str, language: str) -> bool:
            return False

        def is_punct(self, word: str, language: str) -> bool:
            return False

    return AnalyzerEngine(nlp_engine=_PatternOnlyNlpEngine())


class PIIAnonymizer:
    """
    Masks PII in text before it reaches the LLM and restores it afterwards.

    Usage
    -----
    service = PIIAnonymizer()
    masked_text, token_map = service.mask(user_text)
    # ... LLM call with masked_text ...
    restored = service.unmask(llm_response, token_map)
    """

    def __init__(self, entities: list[str] | None = None, language: str = "en") -> None:
        self._entities = entities or DEFAULT_ENTITIES
        self._language = language

    def mask(self, text: str) -> tuple[str, dict[str, Any]]:
        """
        Replace PII spans with unique anonymization tokens.
        Returns (masked_text, token_map). Pass token_map unchanged to unmask().
        Returns (text, {}) when no PII is detected.
        """
        if not text:
            return text, {}

        analyzer = _get_engines()
        results = analyzer.analyze(text=text, entities=self._entities, language=self._language)

        if not results:
            return text, {}

        # Presidio may return multiple detections for overlapping spans
        # (e.g., a phone number also matching US_DRIVER_LICENSE).  Keep only
        # the highest-score result for each span region so we never substitute
        # the same characters twice, which would corrupt the output.
        results = sorted(results, key=lambda r: (-r.score, r.start))
        deduplicated: list = []
        for result in results:
            if any(
                result.start < existing.end and result.end > existing.start
                for existing in deduplicated
            ):
                continue
            deduplicated.append(result)

        # Process right-to-left so earlier offsets stay valid after each substitution.
        # Each entity type gets its own counter so two different emails become
        # <EMAIL_ADDRESS_1> and <EMAIL_ADDRESS_2> and can be independently restored.
        entity_counters: dict[str, int] = {}
        items: list[dict[str, Any]] = []
        masked = text

        for result in sorted(deduplicated, key=lambda r: r.start, reverse=True):
            entity_counters[result.entity_type] = entity_counters.get(result.entity_type, 0) + 1
            counter = entity_counters[result.entity_type]
            generator = _FAKE_VALUE_TEMPLATES.get(result.entity_type)
            token = generator(counter) if generator else f"<{result.entity_type}_{counter}>"
            original = text[result.start:result.end]
            masked = masked[:result.start] + token + masked[result.end:]
            items.append({"token": token, "original": original, "entity_type": result.entity_type})

        items.reverse()  # restore left-to-right order
        logger.debug("PIIAnonymizer.mask: %d PII span(s) masked", len(items))
        return masked, {"items": items}

    def redact(self, text: str, entities: list[str] | None = None) -> str:
        """
        Permanently remove PII spans, replacing them with '[REDACTED]'.
        Unlike mask(), this is a one-way operation — original values are discarded.
        Use this at system boundaries to strip sensitive data before it reaches
        any downstream consumer (DB, LLM, logs, WebSocket).
        """
        if not text:
            return text

        target_entities = entities or self._entities
        analyzer = _get_engines()
        results = analyzer.analyze(text=text, entities=target_entities, language=self._language)

        if not results:
            return text

        results = sorted(results, key=lambda r: (-r.score, r.start))
        deduplicated: list = []
        for result in results:
            if any(
                result.start < existing.end and result.end > existing.start
                for existing in deduplicated
            ):
                continue
            deduplicated.append(result)

        redacted = text
        for result in sorted(deduplicated, key=lambda r: r.start, reverse=True):
            redacted = redacted[:result.start] + "[REDACTED]" + redacted[result.end:]

        logger.debug("PIIAnonymizer.redact: %d PII span(s) redacted", len(deduplicated))
        return redacted

    def unmask(self, text: str, token_map: dict[str, Any]) -> str:
        """
        Restore original PII values using the token_map produced by mask().
        Tokens the LLM dropped or altered are left as-is.
        """
        if not text or not token_map:
            return text

        items = token_map.get("items")
        if not items:
            return text

        for item in items:
            token = item.get("token", "")
            original = item.get("original", "")
            if token and original:
                text = text.replace(token, original)

        return text
