"""Email integration package for Scout."""

from scout.mail.client import (
    get_email_credentials,
    save_email_credentials,
    clear_email_credentials,
    test_connection,
    search_emails,
    read_email,
)

__all__ = [
    "get_email_credentials",
    "save_email_credentials",
    "clear_email_credentials",
    "test_connection",
    "search_emails",
    "read_email",
]
