"""Unit tests for importing dataset files into an existing dataset."""
import io
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from starlette.datastructures import UploadFile

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services import dataset_file
from app.services.dataset_file import (
    FILE_IMPORT_TAG,
    MAX_FILE_ERRORS,
    MAX_IMPORT_FILE_BYTES,
    MAX_IMPORT_FILES,
    DatasetUpload,
    conversation_key,
    parse_dataset_file,
    read_uploads,
)
from app.services.test_suite import TestSuiteService


def _turn(message="hi", expected="hello", **extra):
    turn = {"input_data": {"message": message}, **extra}
    if expected is not None:
        turn["expected_output"] = {"value": expected}
    return turn


def _conversation(*turns):
    return {"turns": list(turns)}


def _file(*conversations, **header) -> bytes:
    body = {"kind": "genassist.dataset", "schema_version": 1, **header}
    body["conversations"] = list(conversations)
    return json.dumps(body).encode()


class TestParseDatasetFile:
    def test_reads_conversations_and_turns_in_order(self):
        parsed = parse_dataset_file(
            _file(
                _conversation(_turn("q1", "a1"), _turn("q2", "a2")),
                _conversation(_turn("q3", "a3")),
            )
        )

        assert parsed.status == "ok"
        assert [
            [turn.input_data["message"] for turn in conversation]
            for conversation in parsed.conversations
        ] == [["q1", "q2"], ["q3"]]
        assert parsed.conversations[0][1].expected_output == {"value": "a2"}

    def test_keeps_extra_input_fields(self):
        turn = {"input_data": {"message": "hi", "region": "united-kingdom"}}

        parsed = parse_dataset_file(_file(_conversation(turn)))

        assert parsed.conversations[0][0].input_data == {
            "message": "hi",
            "region": "united-kingdom",
        }

    def test_kind_and_schema_version_are_optional(self):
        raw = json.dumps({"conversations": [_conversation(_turn())]}).encode()

        assert parse_dataset_file(raw).status == "ok"

    def test_tags_gain_the_file_tag_and_lose_reserved_ones(self):
        turn = _turn(tags=["refund", "imported", " refund ", "", FILE_IMPORT_TAG])

        parsed = parse_dataset_file(_file(_conversation(turn)))

        assert parsed.conversations[0][0].tags == ["refund", FILE_IMPORT_TAG]

    def test_an_empty_expected_output_is_stored_as_none(self):
        turn = _turn(expected=None, expected_output={})

        parsed = parse_dataset_file(_file(_conversation(turn)))

        assert parsed.conversations[0][0].expected_output is None

    def test_weight_is_read_as_a_number(self):
        parsed = parse_dataset_file(_file(_conversation(_turn(weight=2))))

        assert parsed.conversations[0][0].weight == 2.0

    @pytest.mark.parametrize("weight", [True, "2", [1]])
    def test_a_weight_that_is_not_a_number_is_rejected(self, weight):
        parsed = parse_dataset_file(_file(_conversation(_turn(weight=weight))))

        assert parsed.status == "failed"
        assert '"weight" must be a number' in parsed.errors[0]

    @pytest.mark.parametrize(
        "kind", ["genassist.evaluation-bundle", "genassist.evaluation-bundle-set"]
    )
    def test_evaluation_bundles_are_sent_to_the_evaluation_import(self, kind):
        parsed = parse_dataset_file(json.dumps({"kind": kind}).encode())

        assert parsed.status == "evaluation_bundle"
        assert parsed.conversations == []
        assert "Evaluations page" in parsed.errors[0]

    @pytest.mark.parametrize("kind", ["something-else", ["genassist.dataset"], 3])
    def test_other_kinds_are_rejected(self, kind):
        parsed = parse_dataset_file(_file(_conversation(_turn()), kind=kind))

        assert parsed.status == "failed"
        assert "not a dataset file" in parsed.errors[0]

    def test_a_newer_schema_version_is_rejected(self):
        parsed = parse_dataset_file(_file(_conversation(_turn()), schema_version=2))

        assert parsed.status == "failed"
        assert "newer version" in parsed.errors[0]

    @pytest.mark.parametrize("version", [0, "1", 1.5, True])
    def test_a_malformed_schema_version_is_rejected(self, version):
        parsed = parse_dataset_file(_file(_conversation(_turn()), schema_version=version))

        assert parsed.errors == ['"schema_version" must be a whole number, such as 1.']

    def test_invalid_json_names_the_position(self):
        parsed = parse_dataset_file(b'{\n  "conversations": [\n    {"turns": [}\n  ]\n}')

        assert parsed.status == "failed"
        assert parsed.errors[0].startswith("The file is not valid JSON (line 3,")

    @pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e400"])
    def test_numbers_json_cannot_hold_are_rejected(self, literal):
        raw = (
            '{"conversations": [{"turns": [{"input_data": {"message": "hi", "score": '
            + literal
            + "}}]}]}"
        ).encode()

        parsed = parse_dataset_file(raw)

        assert parsed.status == "failed"
        assert len(parsed.errors) == 1

    def test_text_that_is_not_utf8_is_rejected(self):
        parsed = parse_dataset_file('{"conversations": "é"}'.encode("latin-1"))

        assert parsed.errors == ["The file is not UTF-8 text."]

    def test_a_byte_order_mark_is_accepted(self):
        parsed = parse_dataset_file(b"\xef\xbb\xbf" + _file(_conversation(_turn())))

        assert parsed.status == "ok"

    @pytest.mark.parametrize("raw", [b"", b"  \n"])
    def test_an_empty_file_is_rejected(self, raw):
        assert parse_dataset_file(raw).errors == ["The file is empty."]

    def test_the_top_level_must_be_an_object(self):
        parsed = parse_dataset_file(json.dumps([_conversation(_turn())]).encode())

        assert parsed.status == "failed"
        assert '"conversations" list' in parsed.errors[0]

    @pytest.mark.parametrize(
        "conversations, error",
        [
            (None, 'The file has no "conversations" list.'),
            ({}, 'The file has no "conversations" list.'),
            ([], "The file has no conversations."),
        ],
    )
    def test_conversations_must_be_a_non_empty_list(self, conversations, error):
        raw = json.dumps({"conversations": conversations}).encode()

        assert parse_dataset_file(raw).errors == [error]

    def test_problems_name_the_conversation_and_turn(self):
        parsed = parse_dataset_file(
            _file(
                _conversation(_turn()),
                "not an object",
                {"turns": []},
                _conversation(
                    _turn(),
                    {"input_data": {"message": 3}, "expected": "x"},
                ),
            )
        )

        assert parsed.status == "failed"
        assert parsed.conversations == []
        assert parsed.errors == [
            "Conversation 2 is not an object.",
            "Conversation 3 has no turns.",
            'Conversation 4, turn 2: unknown field "expected"; "message" must be text.',
        ]

    @pytest.mark.parametrize("input_data", [None, {}, "hi", ["hi"]])
    def test_input_data_must_be_a_non_empty_object(self, input_data):
        parsed = parse_dataset_file(_file(_conversation({"input_data": input_data})))

        assert parsed.errors == [
            'Conversation 1, turn 1: "input_data" must be an object with at least one field.'
        ]

    def test_a_single_turn_may_omit_the_message(self):
        parsed = parse_dataset_file(
            _file(_conversation({"input_data": {"document": "invoice.pdf"}}))
        )

        assert parsed.status == "ok"

    def test_every_turn_of_a_longer_conversation_needs_a_message(self):
        parsed = parse_dataset_file(
            _file(_conversation(_turn(), {"input_data": {"document": "invoice.pdf"}}))
        )

        assert parsed.status == "failed"
        assert parsed.errors[0].startswith('Conversation 1, turn 2: "input_data" needs a "message"')

    def test_expected_output_must_be_an_object(self):
        parsed = parse_dataset_file(
            _file(_conversation(_turn(expected=None, expected_output="hello")))
        )

        assert '"expected_output" must be an object' in parsed.errors[0]

    def test_tags_must_be_text(self):
        parsed = parse_dataset_file(_file(_conversation(_turn(tags=["ok", 1]))))

        assert '"tags" must be a list of text values' in parsed.errors[0]

    def test_the_error_list_is_capped(self):
        bad = [_conversation({"input_data": {}}) for _ in range(MAX_FILE_ERRORS + 3)]

        parsed = parse_dataset_file(_file(*bad))

        assert len(parsed.errors) == MAX_FILE_ERRORS + 1
        assert parsed.errors[-1] == "3 more problems not listed."


class TestConversationKey:
    def test_field_order_does_not_matter(self):
        first = conversation_key([({"message": "hi", "region": "uk"}, {"value": "x"})])
        second = conversation_key([({"region": "uk", "message": "hi"}, {"value": "x"})])

        assert first == second

    def test_an_empty_expected_output_matches_a_missing_one(self):
        assert conversation_key([({"message": "hi"}, {})]) == conversation_key(
            [({"message": "hi"}, None)]
        )

    def test_turn_order_matters(self):
        one, two = ({"message": "1"}, None), ({"message": "2"}, None)

        assert conversation_key([one, two]) != conversation_key([two, one])


def _upload(content: bytes, filename="dataset.json") -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename)


class TestReadUploads:
    @pytest.mark.asyncio
    async def test_reads_each_file(self):
        uploads = await read_uploads([_upload(b"{}", "a.json"), _upload(b"[]", "b.JSON")])

        assert [(u.filename, u.content, u.error) for u in uploads] == [
            ("a.json", b"{}", None),
            ("b.JSON", b"[]", None),
        ]

    @pytest.mark.asyncio
    async def test_too_many_files_fail_the_request(self):
        files = [_upload(b"{}", f"{n}.json") for n in range(MAX_IMPORT_FILES + 1)]

        with pytest.raises(AppException) as raised:
            await read_uploads(files)

        assert raised.value.error_key == ErrorKey.DATASET_FILE_IMPORT_INVALID

    @pytest.mark.asyncio
    async def test_a_file_that_is_not_json_is_refused_alone(self):
        uploads = await read_uploads([_upload(b"a,b", "data.csv"), _upload(b"{}")])

        assert uploads[0].error == "Only .json files can be imported."
        assert uploads[1].error is None

    @pytest.mark.asyncio
    async def test_an_oversized_file_is_refused_alone(self):
        uploads = await read_uploads(
            [_upload(b" " * (MAX_IMPORT_FILE_BYTES + 1), "big.json"), _upload(b"{}")]
        )

        assert uploads[0].error == "The file is larger than 5 MB."
        assert uploads[0].content == b""
        assert uploads[1].error is None

    @pytest.mark.asyncio
    async def test_files_over_the_total_size_fail_the_request(self, monkeypatch):
        monkeypatch.setattr(dataset_file, "MAX_IMPORT_TOTAL_BYTES", 10)

        with pytest.raises(AppException) as raised:
            await read_uploads([_upload(b"123456"), _upload(b"123456")])

        assert raised.value.error_key == ErrorKey.DATASET_FILE_IMPORT_INVALID

    @pytest.mark.asyncio
    async def test_the_name_drops_any_folder(self):
        uploads = await read_uploads([_upload(b"{}", "C:\\exports\\refunds.json")])

        assert uploads[0].filename == "refunds.json"


def _service() -> TestSuiteService:
    return TestSuiteService(
        suite_repo=AsyncMock(),
        case_repo=AsyncMock(),
        run_repo=AsyncMock(),
        result_repo=AsyncMock(),
        evaluation_repo=AsyncMock(),
        tool_rule_result_repo=AsyncMock(),
        workflow_service=AsyncMock(),
        conversation_repo=AsyncMock(),
    )


def _existing_case(message, expected, conversation_id, turn_index=0):
    return SimpleNamespace(
        id=uuid4(),
        source_conversation_id=conversation_id,
        turn_index=turn_index,
        input_data={"message": message},
        expected_output={"value": expected} if expected else None,
        created_at=datetime(2026, 1, 1),
    )


def _arrange(service, existing=None):
    suite_id = uuid4()
    service.suite_repo.get_by_id.return_value = SimpleNamespace(id=suite_id)
    service.case_repo.get_all_for_suite.return_value = existing or []
    return suite_id


def _inserted(service):
    service.case_repo.add_many.assert_awaited_once()
    return service.case_repo.add_many.await_args.args[0]


class TestFileImport:
    @pytest.mark.asyncio
    async def test_preview_counts_what_would_be_added_without_writing(self):
        service = _service()
        suite_id = _arrange(service)
        upload = DatasetUpload(
            "a.json",
            content=_file(
                _conversation(_turn("q1"), _turn("q2")), _conversation(_turn("q3"))
            ),
        )

        result = await service.preview_cases_from_files(suite_id, [upload])

        assert (result.conversations, result.turns, result.duplicates) == (2, 3, 0)
        assert result.files[0].status == "ok"
        assert result.error is None
        service.case_repo.add_many.assert_not_awaited()
        service.case_repo.create_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_import_threads_each_conversation_under_a_new_id(self):
        service = _service()
        suite_id = _arrange(service)
        upload = DatasetUpload(
            "a.json",
            content=_file(
                _conversation(_turn("q1"), _turn("q2", tags=["refund"], weight=2)),
                _conversation(_turn("q3")),
            ),
        )

        result = await service.import_cases_from_files(suite_id, [upload])

        cases = _inserted(service)
        assert [case.input_data["message"] for case in cases] == ["q1", "q2", "q3"]
        assert [case.turn_index for case in cases] == [0, 1, 0]
        assert cases[0].source_conversation_id == cases[1].source_conversation_id
        assert cases[2].source_conversation_id != cases[0].source_conversation_id
        assert all(case.suite_id == suite_id for case in cases)
        assert cases[0].tags == [FILE_IMPORT_TAG]
        assert cases[1].tags == ["refund", FILE_IMPORT_TAG]
        assert cases[1].weight == 2.0
        assert (result.conversations, result.turns) == (2, 3)

    @pytest.mark.asyncio
    async def test_conversations_the_dataset_already_holds_are_skipped(self):
        service = _service()
        held = uuid4()
        suite_id = _arrange(
            service,
            existing=[
                _existing_case("q2", "a2", held, turn_index=1),
                _existing_case("q1", "a1", held, turn_index=0),
            ],
        )
        upload = DatasetUpload(
            "a.json",
            content=_file(
                _conversation(_turn("q1", "a1"), _turn("q2", "a2")),
                _conversation(_turn("q1", "a1")),
            ),
        )

        result = await service.import_cases_from_files(suite_id, [upload])

        cases = _inserted(service)
        assert len(cases) == 1
        assert result.duplicates == 1
        assert (result.files[0].conversations, result.files[0].duplicates) == (1, 1)

    @pytest.mark.asyncio
    async def test_a_conversation_repeated_across_files_is_added_once(self):
        service = _service()
        suite_id = _arrange(service)
        content = _file(_conversation(_turn("q1")))

        result = await service.import_cases_from_files(
            suite_id, [DatasetUpload("a.json", content), DatasetUpload("b.json", content)]
        )

        assert len(_inserted(service)) == 1
        # Repeating another file is not the same as being in the dataset.
        assert [entry.duplicates for entry in result.files] == [0, 0]
        assert [entry.repeated for entry in result.files] == [0, 1]
        assert [entry.repeated_from for entry in result.files] == [[], [0]]
        assert (result.duplicates, result.repeated) == (0, 1)

    @pytest.mark.asyncio
    async def test_a_conversation_repeated_within_one_file_points_at_itself(self):
        service = _service()
        suite_id = _arrange(service)
        content = _file(_conversation(_turn("q1")), _conversation(_turn("q1")))

        result = await service.preview_cases_from_files(
            suite_id, [DatasetUpload("a.json", content)]
        )

        entry = result.files[0]
        assert (entry.conversations, entry.repeated, entry.repeated_from) == (1, 1, [0])

    @pytest.mark.asyncio
    async def test_being_in_the_dataset_wins_over_being_repeated(self):
        service = _service()
        suite_id = _arrange(service, existing=[_existing_case("q1", "hello", uuid4())])
        content = _file(_conversation(_turn("q1")))

        result = await service.preview_cases_from_files(
            suite_id, [DatasetUpload("a.json", content), DatasetUpload("b.json", content)]
        )

        assert [entry.duplicates for entry in result.files] == [1, 1]
        assert [entry.repeated for entry in result.files] == [0, 0]

    @pytest.mark.asyncio
    async def test_a_file_with_problems_does_not_block_the_others(self):
        service = _service()
        suite_id = _arrange(service)

        result = await service.import_cases_from_files(
            suite_id,
            [
                DatasetUpload("broken.json", b"{not json"),
                DatasetUpload("big.json", error="The file is larger than 5 MB."),
                DatasetUpload("good.json", _file(_conversation(_turn("q1")))),
            ],
        )

        assert [entry.status for entry in result.files] == ["failed", "failed", "ok"]
        assert result.files[1].errors == ["The file is larger than 5 MB."]
        assert result.failed_files == 2
        assert len(_inserted(service)) == 1

    @pytest.mark.asyncio
    async def test_an_evaluation_bundle_is_reported_and_not_imported(self):
        service = _service()
        suite_id = _arrange(service)
        bundle = json.dumps({"kind": "genassist.evaluation-bundle-set"}).encode()

        result = await service.import_cases_from_files(
            suite_id, [DatasetUpload("parker-evaluations.json", bundle)]
        )

        assert result.files[0].status == "evaluation_bundle"
        assert result.failed_files == 1
        service.case_repo.add_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_too_many_turns_block_the_import(self, monkeypatch):
        monkeypatch.setattr(dataset_file, "MAX_IMPORT_TURNS", 2)
        service = _service()
        suite_id = _arrange(service)
        upload = DatasetUpload(
            "a.json", _file(_conversation(_turn("q1"), _turn("q2"), _turn("q3")))
        )

        preview = await service.preview_cases_from_files(suite_id, [upload])
        with pytest.raises(AppException) as raised:
            await service.import_cases_from_files(suite_id, [upload])

        assert "at most 2" in preview.error
        assert raised.value.error_key == ErrorKey.DATASET_FILE_IMPORT_INVALID
        service.case_repo.add_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_nothing_new_writes_nothing(self):
        service = _service()
        suite_id = _arrange(
            service, existing=[_existing_case("q1", "hello", uuid4())]
        )

        result = await service.import_cases_from_files(
            suite_id, [DatasetUpload("a.json", _file(_conversation(_turn("q1"))))]
        )

        assert (result.conversations, result.duplicates) == (0, 1)
        service.case_repo.add_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_missing_dataset_is_not_found(self):
        service = _service()
        service.suite_repo.get_by_id.return_value = None

        with pytest.raises(AppException) as raised:
            await service.import_cases_from_files(
                uuid4(), [DatasetUpload("a.json", _file(_conversation(_turn())))]
            )

        assert raised.value.status_code == 404
        service.case_repo.get_all_for_suite.assert_not_awaited()
        service.case_repo.add_many.assert_not_awaited()
