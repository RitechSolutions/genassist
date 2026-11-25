"""Email address checks shared by integrations."""

from email_validator import EmailNotValidError, validate_email


def is_valid_email_address(value: str) -> bool:
    """Whether ``value`` is a plain ASCII email address. Checks the format only, not the mailbox."""
    try:
        validate_email(value, check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError:
        return False
    return True
