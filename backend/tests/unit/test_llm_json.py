"""One JSON object or nothing: what an LLM reply must look like to be usable"""

import pytest

from app.core.utils.llm_json import _MAX_ESCAPE_REPAIRS, parse_json_object_reply


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

    @pytest.mark.parametrize(
        "reply",
        [
            'Here is the prompt: {"a": 1}',
            '{"a": 1}\n\nHope that helps!',
            'Sure thing:\n```json\n{"a": 1}\n```',
            '```json\n{"a": 1}\n```\nHope that helps!',
        ],
    )
    def test_prose_around_the_object_is_rejected(self, reply):
        with pytest.raises(ValueError):
            parse_json_object_reply(reply)

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

    def test_a_reply_nested_past_the_parser_depth_is_rejected(self):
        depth = 50_000
        with pytest.raises(ValueError):
            parse_json_object_reply('{"a": ' + "[" * depth + "]" * depth + "}")

    def test_an_empty_reply_is_rejected(self):
        with pytest.raises(ValueError):
            parse_json_object_reply("")

    def test_a_raw_newline_inside_a_string_needs_the_lenient_mode(self):
        reply = '{"a": "x\ny"}'
        with pytest.raises(ValueError):
            parse_json_object_reply(reply)
        assert parse_json_object_reply(reply, strict=False) == {"a": "x\ny"}

    @pytest.mark.parametrize(
        "reply",
        ['{"a": "x\\ny",\\n  "b": "z"}', '{\\n  "a": "x\\ny", "b": "z"\\r\\n}'],
    )
    def test_an_escaped_newline_between_members_needs_the_lenient_mode(self, reply):
        with pytest.raises(ValueError):
            parse_json_object_reply(reply)
        assert parse_json_object_reply(reply, strict=False) == {"a": "x\ny", "b": "z"}

    def test_the_lenient_mode_gives_up_after_the_repair_cap(self):
        def reply(separators):
            return "{" + ",\\n ".join(f'"k{i}": {i}' for i in range(separators + 1)) + "}"

        assert len(parse_json_object_reply(reply(_MAX_ESCAPE_REPAIRS), strict=False)) == _MAX_ESCAPE_REPAIRS + 1
        with pytest.raises(ValueError):
            parse_json_object_reply(reply(_MAX_ESCAPE_REPAIRS + 1), strict=False)
