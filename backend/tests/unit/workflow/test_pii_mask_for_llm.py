"""PIIAnonymizerMixin._mask_for_llm — return-path masking + token accumulation"""

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

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


def test_mask_for_llm_continues_numbering_from_accumulated_items():
    node = _Node()
    node._pii_prompt_token_items = [
        {"token": "<EMAIL_ADDRESS_1>", "original": "a@b.com", "entity_type": "EMAIL_ADDRESS"}
    ]
    fake = MagicMock()
    fake.mask.return_value = ("x", {"items": []})
    with patch.object(mixin_mod, "_service", fake):
        node._mask_for_llm("x")
    assert fake.mask.call_args.kwargs["existing_items"] == node._pii_prompt_token_items


class _FakeBase:
    async def execute(self, direct_input: Any = None) -> Any:
        return await self.process(self._config)


class _MidRunMaskNode(PIIAnonymizerMixin, _FakeBase):
    """Masks a child result mid-process and echoes the token, like the delegation loop"""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    async def process(self, config: Dict[str, Any]) -> str:
        return f"echo {self._mask_for_llm('Reach me at a@b.com')}"


@pytest.mark.asyncio
async def test_mask_for_llm_items_restored_in_final_result():
    fake = MagicMock()

    def _mask(text, existing_items=None):
        if "a@b.com" not in text:
            return text, {}
        return (
            text.replace("a@b.com", "<EMAIL_ADDRESS_1>"),
            {"items": [{"token": "<EMAIL_ADDRESS_1>", "original": "a@b.com", "entity_type": "EMAIL_ADDRESS"}]},
        )

    def _unmask(text, token_map):
        for item in token_map.get("items", []):
            text = text.replace(item["token"], item["original"])
        return text

    fake.mask.side_effect = _mask
    fake.unmask.side_effect = _unmask

    node = _MidRunMaskNode({"piiMasking": True, "userPrompt": "no pii here"})
    with patch.object(mixin_mod, "_service", fake):
        result = await node.execute()

    assert result == "echo Reach me at a@b.com"
    assert "<EMAIL_ADDRESS_1>" not in result
