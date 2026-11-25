"""Tests for the shared email address check."""

import pytest

from app.core.utils.email_utils import is_valid_email_address


@pytest.mark.parametrize("address", [
    "jane@example.com",
    "jane.doe+tickets@example.co.uk",
    "JANE_DOE@Example.COM",
    "j@mail.example.org",
])
def test_real_looking_addresses_are_valid(address):
    assert is_valid_email_address(address) is True


@pytest.mark.parametrize("value", [
    "unknown",
    "email_here",
    "no email",
    "n/a",
    "jane@example",
    "jane example.com",
    "jane@example.com or jane@example.org",
    "jane@example.com,uk",
    "jané@example.com",
    "07000000000",
    "",
])
def test_other_values_are_not_valid(value):
    assert is_valid_email_address(value) is False
