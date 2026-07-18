"""PIIAnonymizerMixin._mask_for_llm — return-path masking + token accumulation"""

from unittest.mock import MagicMock, patch

from app.modules.workflow.engine import pii_anonymizer_mixin as mixin_mod
from app.modules.workflow.engine.pii_anonymizer_mixin import PIIAnonymizerMixin


class _Node(PIIAnonymizerMixin):
    pass


def test_mask_for_llm_accumulates_prompt_tokens():
    node = _Node()
    node._pii_prompt_token_items = []
    item = {"placeholder": "<EMAIL_ADDRESS_1>", "value": "a@b.com"}
    fake = MagicMock()
    fake.mask.return_value = ("email <EMAIL_ADDRESS_1>", {"items": [item]})
    with patch.object(mixin_mod, "_service", fake):
        out = node._mask_for_llm("email a@b.com")
    assert out == "email <EMAIL_ADDRESS_1>"
    assert node._pii_prompt_token_items == [item]


def test_mask_for_llm_noop_on_empty_or_no_pii():
    node = _Node()
    node._pii_prompt_token_items = []
    assert node._mask_for_llm("") == ""
    fake = MagicMock()
    fake.mask.return_value = ("plain text", {"items": []})
    with patch.object(mixin_mod, "_service", fake):
        assert node._mask_for_llm("plain text") == "plain text"
    assert node._pii_prompt_token_items == []
