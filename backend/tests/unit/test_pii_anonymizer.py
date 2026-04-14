"""Unit tests for PIIAnonymizer. Presidio analyzer is mocked."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.modules.workflow.engine.pii_anonymizer import PIIAnonymizer


def _make_analyzer_result(start: int, end: int, entity_type: str, score: float = 1.0):
    r = MagicMock()
    r.start = start
    r.end = end
    r.entity_type = entity_type
    r.score = score
    return r


class TestMask:
    def test_returns_original_when_no_pii_detected(self):
        svc = PIIAnonymizer()
        analyzer = MagicMock()
        analyzer.analyze.return_value = []

        with patch(
            "app.modules.workflow.engine.pii_anonymizer._get_engines",
            return_value=analyzer,
        ):
            masked, token_map = svc.mask("Hello, how can I help?")

        assert masked == "Hello, how can I help?"
        assert token_map == {}

    def test_returns_original_on_empty_string(self):
        svc = PIIAnonymizer()
        masked, token_map = svc.mask("")
        assert masked == ""
        assert token_map == {}

    def test_masks_single_pii_span(self):
        original = "My email is alice@example.com"
        svc = PIIAnonymizer()
        analyzer = MagicMock()
        analyzer.analyze.return_value = [
            _make_analyzer_result(start=12, end=29, entity_type="EMAIL_ADDRESS")
        ]

        with patch(
            "app.modules.workflow.engine.pii_anonymizer._get_engines",
            return_value=analyzer,
        ):
            masked, token_map = svc.mask(original)

        assert masked == "My email is johndoe1@example.com"
        assert len(token_map["items"]) == 1
        assert token_map["items"][0]["token"] == "johndoe1@example.com"
        assert token_map["items"][0]["original"] == "alice@example.com"
        assert token_map["items"][0]["entity_type"] == "EMAIL_ADDRESS"

    def test_masks_multiple_pii_spans(self):
        original = "bob@example.com called 555-867-5309"
        svc = PIIAnonymizer()
        analyzer = MagicMock()
        analyzer.analyze.return_value = [
            _make_analyzer_result(0, 15, "EMAIL_ADDRESS"),
            _make_analyzer_result(23, 35, "PHONE_NUMBER"),
        ]

        with patch(
            "app.modules.workflow.engine.pii_anonymizer._get_engines",
            return_value=analyzer,
        ):
            masked, token_map = svc.mask(original)

        assert "johndoe1@example.com" in masked
        assert "(555) 010-0001" in masked
        assert "bob@example.com" not in masked
        assert "555-867-5309" not in masked
        assert len(token_map["items"]) == 2

    def test_two_emails_get_unique_tokens(self):
        original = "From alice@example.com to bob@example.com"
        svc = PIIAnonymizer()
        analyzer = MagicMock()
        analyzer.analyze.return_value = [
            _make_analyzer_result(5, 22, "EMAIL_ADDRESS"),
            _make_analyzer_result(26, 41, "EMAIL_ADDRESS"),
        ]

        with patch(
            "app.modules.workflow.engine.pii_anonymizer._get_engines",
            return_value=analyzer,
        ):
            masked, token_map = svc.mask(original)

        tokens = [item["token"] for item in token_map["items"]]
        assert len(set(tokens)) == 2, "each occurrence must get a unique token"
        assert "johndoe1@example.com" in masked
        assert "johndoe2@example.com" in masked

    def test_token_map_is_json_serializable(self):
        original = "IBAN: DE89370400440532013000"
        svc = PIIAnonymizer()
        analyzer = MagicMock()
        analyzer.analyze.return_value = [
            _make_analyzer_result(6, 28, "IBAN_CODE")
        ]

        with patch(
            "app.modules.workflow.engine.pii_anonymizer._get_engines",
            return_value=analyzer,
        ):
            _, token_map = svc.mask(original)

        json.dumps(token_map)  # must not raise


class TestUnmask:
    def test_returns_original_on_empty_text(self):
        assert PIIAnonymizer().unmask("", {"items": []}) == ""

    def test_returns_original_on_empty_token_map(self):
        assert PIIAnonymizer().unmask("some text", {}) == "some text"

    def test_restores_single_pii(self):
        svc = PIIAnonymizer()
        token_map = {
            "items": [
                {"token": "johndoe1@example.com", "original": "alice@example.com", "entity_type": "EMAIL_ADDRESS"}
            ]
        }
        result = svc.unmask("Your email johndoe1@example.com is on file.", token_map)
        assert result == "Your email alice@example.com is on file."

    def test_restores_two_different_emails(self):
        svc = PIIAnonymizer()
        token_map = {
            "items": [
                {"token": "johndoe1@example.com", "original": "alice@example.com", "entity_type": "EMAIL_ADDRESS"},
                {"token": "johndoe2@example.com", "original": "bob@example.com", "entity_type": "EMAIL_ADDRESS"},
            ]
        }
        result = svc.unmask(
            "From johndoe1@example.com to johndoe2@example.com.",
            token_map,
        )
        assert result == "From alice@example.com to bob@example.com."

    def test_returns_intact_when_token_absent_from_response(self):
        svc = PIIAnonymizer()
        token_map = {
            "items": [{"token": "johndoe1@example.com", "original": "bob@example.com", "entity_type": "EMAIL_ADDRESS"}]
        }
        result = svc.unmask("I cannot find any email address in your message.", token_map)
        assert "bob@example.com" not in result

    def test_round_trip(self):
        original = "Call me at 555-123-4567 or email bob@test.com."
        svc = PIIAnonymizer()
        analyzer_m = MagicMock()
        analyzer_m.analyze.return_value = [
            _make_analyzer_result(11, 23, "PHONE_NUMBER"),
            _make_analyzer_result(33, 45, "EMAIL_ADDRESS"),
        ]

        with patch(
            "app.modules.workflow.engine.pii_anonymizer._get_engines",
            return_value=analyzer_m,
        ):
            masked, token_map = svc.mask(original)

        assert "555-123-4567" not in masked
        assert "bob@test.com" not in masked

        restored = svc.unmask(masked, token_map)
        assert restored == original
