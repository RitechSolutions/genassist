"""Client-safe handling of read-only SQL policy rejections."""

from app.core.exceptions.error_messages import ErrorKey, get_error_message
from app.core.exceptions.error_policy import (
    CLIENT_SAFE_DETAIL_KEYS,
    READ_ONLY_SQL_BLOCKED_DETAIL_PREFIX,
    client_safe_error_detail,
    exception_location,
    sanitize_error_detail,
)
from app.core.exceptions.exception_classes import AppException
from app.core.exceptions.exception_handler import _response_error_detail
from app.modules.integration.database.read_only_sql import (
    READ_ONLY_SQL_BLOCKED_PREFIX,
    read_only_sql_blocked_message,
    validate_read_only_sql,
)


def test_read_only_sql_blocked_is_client_safe_key():
    assert ErrorKey.READ_ONLY_SQL_BLOCKED in CLIENT_SAFE_DETAIL_KEYS
    assert ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED in CLIENT_SAFE_DETAIL_KEYS
    assert ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID in CLIENT_SAFE_DETAIL_KEYS
    assert ErrorKey.ML_EXTRACT_QUERY_FAILED in CLIENT_SAFE_DETAIL_KEYS
    assert ErrorKey.ML_EXTRACT_FILE_UNAVAILABLE in CLIENT_SAFE_DETAIL_KEYS
    assert ErrorKey.ML_EXTRACT_FAILED not in CLIENT_SAFE_DETAIL_KEYS
    assert ErrorKey.INTERNAL_ERROR not in CLIENT_SAFE_DETAIL_KEYS
    assert READ_ONLY_SQL_BLOCKED_DETAIL_PREFIX == READ_ONLY_SQL_BLOCKED_PREFIX


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
    assert client_safe_error_detail(error) == detail


def test_extract_limit_detail_is_returned_outside_dev(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    detail = (
        "The database query returned more than 2,000,000 rows, which exceeds "
        "the limit of 2,000,000. Add a filter or LIMIT, or raise ML_EXTRACT_MAX_ROWS."
    )
    error = AppException(
        error_key=ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED,
        error_detail=detail,
    )
    assert _response_error_detail(error) == detail


def test_internal_driver_failure_with_password_is_not_public(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    error = AppException(
        error_key=ErrorKey.INTERNAL_ERROR,
        status_code=500,
        error_detail="could not connect password=secret host=db.internal",
    )
    assert _response_error_detail(error) is None
    assert client_safe_error_detail(error) is None
    assert "secret" not in (get_error_message(ErrorKey.INTERNAL_ERROR) or "")


def test_workflow_detail_policy_stays_strict_in_development(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    error = AppException(
        error_key=ErrorKey.INTERNAL_ERROR,
        status_code=500,
        error_detail="could not connect password=secret host=db.internal",
    )

    # The normal dev exception envelope may contain a sanitized diagnostic, but
    # workflow state is a successful response and must never publish it.
    assert _response_error_detail(error) == (
        "could not connect password=*** host=db.internal"
    )
    assert client_safe_error_detail(error) is None


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
    assert "secret" not in sanitize_error_detail("password=secret extra")
    assert "password=***" in sanitize_error_detail("password=secret extra")


def test_exception_location_excludes_the_exception_message():
    try:
        raise RuntimeError("password=secret host=db.internal")
    except RuntimeError as error:
        location = exception_location(error)

    assert location.startswith("RuntimeError at ")
    assert ".py:" in location
    assert "password" not in location
    assert "secret" not in location
