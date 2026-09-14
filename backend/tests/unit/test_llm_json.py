"""One JSON object or nothing: what an LLM reply must look like to be usable"""

import time

import pytest

from app.core.utils.llm_json import parse_json_object_reply


class TestParseJsonObjectReply:
    def test_reads_a_bare_object(self):
        assert parse_json_object_reply('{"improved_prompt": "x", "explanation": "y"}') == {
            "improved_prompt": "x",
            "explanation": "y",
        }

    def test_reads_an_object_inside_a_complete_fence(self):
        assert parse_json_object_reply('```json\n{"a": 1}\n```') == {"a": 1}

    def test_reads_an_object_inside_an_unlabelled_fence(self):
        assert parse_json_object_reply('```\n{"a": 1}\n```') == {"a": 1}

    def test_an_unbalanced_fence_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply('```json\n{"a": 1}')

    def test_an_array_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply('[{"a": 1}]')

    def test_a_scalar_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply('"just a string"')

    def test_leading_prose_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply('Here is the prompt: {"a": 1}')

    def test_trailing_prose_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply('{"a": 1}\n\nHope that helps!')

    def test_prose_outside_a_complete_fence_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply('Sure thing:\n```json\n{"a": 1}\n```')

    def test_a_complete_fence_followed_by_prose_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply('```json\n{"a": 1}\n```\nHope that helps!')

    def test_two_objects_are_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply('{"a": 1}{"b": 2}')

    @pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e400", "-1e400"])
    def test_a_non_finite_number_is_rejected(self, number):
        with pytest.raises(ValueError):
            parse_json_object_reply('{"a": %s}' % number)

    @pytest.mark.parametrize(
        ("number", "expected"),
        [("1.5", 1.5), ("1e10", 1e10), ("1E-5", 1e-5), ("-2.5", -2.5), ("9007199254740993", 9007199254740993)],
    )
    def test_ordinary_numbers_still_parse(self, number, expected):
        assert parse_json_object_reply('{"a": %s}' % number)["a"] == expected

    def test_an_empty_reply_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply("")

    def test_a_long_whitespace_run_inside_a_fence_is_rejected_promptly(self):
        reply = "```json" + (" " * 20_000) + "```done"

        started = time.perf_counter()
        with pytest.raises(ValueError):
            parse_json_object_reply(reply)
        assert time.perf_counter() - started < 2.0
