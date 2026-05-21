from app.core.utils.notification_ids import (
    is_valid_notification_id,
    normalize_notification_ids,
)


def test_is_valid_notification_id_accepts_known_prefixes():
    assert is_valid_notification_id("conversation_started:550e8400-e29b-41d4-a716-446655440000")
    assert is_valid_notification_id("workflow_failed:pipeline:550e8400-e29b-41d4-a716-446655440000")


def test_is_valid_notification_id_rejects_unknown_prefix():
    assert not is_valid_notification_id("unknown:abc")
    assert not is_valid_notification_id("")


def test_normalize_notification_ids_dedupes_and_filters():
    raw = [
        "conversation_started:550e8400-e29b-41d4-a716-446655440000",
        "conversation_started:550e8400-e29b-41d4-a716-446655440000",
        "bad-id",
        "",
    ]
    assert normalize_notification_ids(raw) == [
        "conversation_started:550e8400-e29b-41d4-a716-446655440000"
    ]
