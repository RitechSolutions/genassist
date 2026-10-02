"""Payload-to-input mapping shared by the ingress route and the node."""

from app.modules.workflow.webhook_trigger_mapping import (
    build_envelope,
    build_trigger_input,
    extract_idempotency_key,
    get_path,
    parse_sample_payload,
    resolve_thread_id,
)


def _envelope(body=None, headers=None, query=None):
    return build_envelope(method="POST", headers=headers or {}, query=query or {}, body=body or {})


class TestGetPath:
    def test_nested_dicts_and_list_indexes(self):
        data = {"body": {"items": [{"id": "a"}, {"id": "b"}]}}
        assert get_path(data, "body.items.1.id") == (True, "b")

    def test_headers_match_case_insensitively(self):
        data = {"headers": {"x-event-type": "order.created"}}
        assert get_path(data, "headers.X-Event-Type") == (True, "order.created")

    def test_missing_path_is_distinguishable_from_null(self):
        assert get_path({"a": None}, "a") == (True, None)
        assert get_path({"a": None}, "b") == (False, None)
        assert get_path({"a": [1]}, "a.x") == (False, None)
        assert get_path({"a": 1}, "") == (False, None)


class TestBuildTriggerInput:
    def test_envelope_always_present_and_message_absent_when_unmapped(self):
        input_data, errors = build_trigger_input(_envelope(body={"x": 1}), {})
        assert errors == []
        assert input_data["webhook"]["body"] == {"x": 1}
        # No message key: the engine will not write this run to conversation memory.
        assert "message" not in input_data

    def test_field_mappings_defaults_and_required(self):
        node_data = {
            "fieldMappings": [
                {"key": "order_id", "path": "body.order.id", "required": True},
                {"key": "priority", "path": "body.priority", "default": "normal"},
                {"key": "source", "path": "headers.x-source"},
                {"key": "", "path": ""},  # empty editor row is ignored
            ]
        }
        env = _envelope(body={"order": {"id": 42}}, headers={"X-Source": "crm"})
        input_data, errors = build_trigger_input(env, node_data)
        assert errors == []
        assert input_data["order_id"] == 42
        assert input_data["priority"] == "normal"
        assert input_data["source"] == "crm"

    def test_missing_required_field_is_an_error(self):
        node_data = {"fieldMappings": [{"key": "order_id", "path": "body.order.id", "required": True}]}
        _, errors = build_trigger_input(_envelope(body={}), node_data)
        assert errors and "order_id" in errors[0]

    def test_reserved_and_invalid_keys_rejected(self):
        node_data = {
            "fieldMappings": [
                {"key": "webhook", "path": "body.x"},
                {"key": "thread_id", "path": "body.x"},
                {"key": "bad key", "path": "body.x"},
            ]
        }
        input_data, errors = build_trigger_input(_envelope(body={"x": 1}), node_data)
        assert len(errors) == 3
        assert input_data["webhook"]["body"] == {"x": 1}
        assert "thread_id" not in input_data

    def test_message_path_sets_message_and_serialises_objects(self):
        env = _envelope(body={"text": "hello", "obj": {"a": 1}})
        input_data, _ = build_trigger_input(env, {"messagePath": "body.text"})
        assert input_data["message"] == "hello"
        input_data, _ = build_trigger_input(env, {"messagePath": "body.obj"})
        assert input_data["message"] == '{"a": 1}'

    def test_missing_message_falls_back_to_empty_unless_required(self):
        env = _envelope(body={})
        input_data, errors = build_trigger_input(env, {"messagePath": "body.text"})
        assert errors == [] and input_data["message"] == ""
        _, errors = build_trigger_input(env, {"messagePath": "body.text", "messageRequired": True})
        assert errors


class TestThreadAndIdempotency:
    def test_thread_id_from_path(self):
        env = _envelope(body={"conversation": {"id": 7}})
        assert resolve_thread_id(env, {"threadIdPath": "body.conversation.id"}) == "7"
        assert resolve_thread_id(env, {"threadIdPath": "body.nope"}) is None
        assert resolve_thread_id(env, {}) is None

    def test_idempotency_header_wins_over_path(self):
        env = _envelope(body={"event_id": "evt_1"}, headers={"Idempotency-Key": "hdr_1"})
        assert extract_idempotency_key(env, {"idempotencyPath": "body.event_id"}) == "hdr_1"
        env = _envelope(body={"event_id": "evt_1"})
        assert extract_idempotency_key(env, {"idempotencyPath": "body.event_id"}) == "evt_1"
        assert extract_idempotency_key(env, {}) is None


class TestSamplePayload:
    def test_json_text_object_and_garbage(self):
        assert parse_sample_payload({"samplePayload": '{"a": 1}'}) == {"a": 1}
        assert parse_sample_payload({"samplePayload": {"a": 1}}) == {"a": 1}
        assert parse_sample_payload({"samplePayload": "   "}) == {}
        assert parse_sample_payload({"samplePayload": "not json"}) == {"raw": "not json"}
        assert parse_sample_payload({}) == {}
