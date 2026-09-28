"""Client-safe handling of read-only SQL policy rejections."""

from app.core.exceptions.error_messages import ErrorKey, get_error_message
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import (
    _CLIENT_SAFE_DETAIL_KEYS,
    _READ_ONLY_SQL_BLOCKED_DETAIL_PREFIX,
    _response_error_detail,
    _sanitize_public_error_detail,
)
from app.modules.integration.database.read_only_sql import (
    READ_ONLY_SQL_BLOCKED_PREFIX,
    read_only_sql_blocked_message,
    validate_read_only_sql,
)


def test_read_only_sql_blocked_is_client_safe_key():
    assert ErrorKey.READ_ONLY_SQL_BLOCKED in _CLIENT_SAFE_DETAIL_KEYS
    assert ErrorKey.INTERNAL_ERROR not in _CLIENT_SAFE_DETAIL_KEYS
    assert _READ_ONLY_SQL_BLOCKED_DETAIL_PREFIX == READ_ONLY_SQL_BLOCKED_PREFIX


def test_policy_reason_is_returned_outside_dev(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    validation = validate_read_only_sql("DELETE FROM users", "postgresql")
    detail = read_only_sql_blocked_message(validation)
    error = AppException(
        error_key=ErrorKey.READ_ONLY_SQL_BLOCKED,
        status_code=400,
        error_detail=detail,
    )
    assert _response_error_detail(error) == detail
    assert "Delete" in _response_error_detail(error)


def test_internal_driver_failure_with_password_is_not_public(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    error = AppException(
        error_key=ErrorKey.INTERNAL_ERROR,
        status_code=500,
        error_detail="could not connect password=secret host=db.internal",
    )
    assert _response_error_detail(error) is None
    assert "secret" not in (get_error_message(ErrorKey.INTERNAL_ERROR) or "")


def test_read_only_key_does_not_publish_unrelated_detail(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    error = AppException(
        error_key=ErrorKey.READ_ONLY_SQL_BLOCKED,
        status_code=400,
        error_detail="could not connect password=secret host=db.internal",
    )
    assert _response_error_detail(error) is None


def test_unrelated_error_key_detail_stays_hidden(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    error = AppException(
        error_key=ErrorKey.DATASOURCE_NOT_FOUND,
        status_code=400,
        error_detail="password=secret",
    )
    assert _response_error_detail(error) is None


def test_sanitizer_still_redacts_password_patterns():
    assert "secret" not in _sanitize_public_error_detail("password=secret extra")
    assert "password=***" in _sanitize_public_error_detail("password=secret extra")
