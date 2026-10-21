"""Unit tests for Scout Gmail integration."""

from unittest.mock import MagicMock, patch
import pytest

from scout.mail.client import (
    get_email_credentials,
    save_email_credentials,
    clear_email_credentials,
    test_connection as check_email_connection,
    search_emails,
    read_email,
    _decode_header_str,
    _html_to_clean_text,
)
from scout.ai.tools import execute_tool
from scout.ai.acknowledgment import is_actionable_task, generate_acknowledgment


class TestMimeHelpers:
    """Test header decoding and HTML stripping."""

    def test_decode_header_plain(self):
        assert _decode_header_str("Test Subject") == "Test Subject"

    def test_decode_header_encoded(self):
        # RFC 2047 encoded word: "Hello World" in base64
        encoded = "=?utf-8?B?SGVsbG8gV29ybGQ=?="
        assert _decode_header_str(encoded) == "Hello World"

    def test_html_to_clean_text(self):
        html = "<html><body><h1>Welcome!</h1><p>Here is your <b>code</b>: 12345</p><script>alert(1);</script></body></html>"
        text = _html_to_clean_text(html)
        assert "Welcome!" in text
        assert "12345" in text
        assert "alert(1)" not in text


class TestCredentials:
    """Test credential saving, loading, and clearing."""

    @patch("scout.mail.client.set_api_key")
    @patch("scout.mail.client.get_api_key")
    @patch("scout.mail.client.load_config")
    @patch("scout.mail.client.save_config")
    def test_save_and_get_credentials(self, mock_save, mock_load, mock_get_key, mock_set_key):
        mock_load.return_value = {"email": {"address": "test@gmail.com"}}
        mock_get_key.return_value = "abcd efgh ijkl mnop"

        save_email_credentials("test@gmail.com", "abcd efgh ijkl mnop")
        mock_set_key.assert_called_once_with("gmail", "abcdefghijklmnop")

        addr, pwd = get_email_credentials()
        assert addr == "test@gmail.com"
        assert pwd == "abcdefghijklmnop"

    @patch("scout.mail.client.delete_api_key")
    @patch("scout.mail.client.load_config")
    @patch("scout.mail.client.save_config")
    def test_clear_credentials(self, mock_save, mock_load, mock_del_key):
        mock_load.return_value = {"email": {"address": "test@gmail.com"}}
        clear_email_credentials()
        mock_del_key.assert_called_once_with("gmail")
        mock_save.assert_called_once()


class TestImapSearchAndRead:
    """Test search_emails and read_email with mocked IMAP server."""

    @patch("scout.mail.client.get_email_credentials", return_value=("user@gmail.com", "validapppassword"))
    @patch("imaplib.IMAP4_SSL")
    def test_test_connection_success(self, mock_imap_cls, mock_creds):
        mock_mail = MagicMock()
        mock_mail.select.return_value = ("OK", [b"10"])
        mock_imap_cls.return_value = mock_mail

        success, msg = check_email_connection()
        assert success is True
        assert "user@gmail.com" in msg
        mock_mail.login.assert_called_once_with("user@gmail.com", "validapppassword")

    @patch("scout.mail.client.get_email_credentials", return_value=("user@gmail.com", "validapppassword"))
    @patch("imaplib.IMAP4_SSL")
    def test_search_emails(self, mock_imap_cls, mock_creds):
        mock_mail = MagicMock()
        mock_mail.select.return_value = ("OK", [b"10"])
        # Return 2 message IDs: 101, 102
        mock_mail.search.return_value = ("OK", [b"101 102"])
        
        # Raw header bytes for msg 102
        raw_header = (
            b"Subject: Meeting tomorrow\r\n"
            b"From: Alice <alice@example.com>\r\n"
            b"Date: Mon, 19 Oct 2026 10:00:00 +0000\r\n"
            b"To: user@gmail.com\r\n\r\n"
        )
        mock_mail.fetch.return_value = ("OK", [(b"102 (BODY[HEADER] {120}", raw_header), b")"])
        mock_imap_cls.return_value = mock_mail

        results = search_emails(limit=2)
        assert len(results) == 2
        assert results[0]["id"] == "102"
        assert results[0]["subject"] == "Meeting tomorrow"
        assert "alice@example.com" in results[0]["from"]

    @patch("scout.mail.client.get_email_credentials", return_value=("user@gmail.com", "validapppassword"))
    @patch("imaplib.IMAP4_SSL")
    def test_read_email_plain(self, mock_imap_cls, mock_creds):
        mock_mail = MagicMock()
        mock_mail.select.return_value = ("OK", [b"10"])

        raw_email = (
            b"Subject: Invoice #1234\r\n"
            b"From: billing@company.com\r\n"
            b"To: user@gmail.com\r\n"
            b"Date: Mon, 19 Oct 2026 10:30:00 +0000\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Please find your invoice attached for $150.00.\r\n"
        )
        mock_mail.fetch.return_value = ("OK", [(b"102 (BODY[] {200}", raw_email)])
        mock_imap_cls.return_value = mock_mail

        data = read_email("102")
        assert data["id"] == "102"
        assert data["subject"] == "Invoice #1234"
        assert "billing@company.com" in data["from"]
        assert "invoice attached for $150.00" in data["body"]


class TestEmailToolsAndAcknowledgment:
    """Test AI tools execution and task acknowledgment for email requests."""

    @patch("scout.mail.client.search_emails")
    def test_tool_search_emails(self, mock_search):
        mock_search.return_value = [
            {"id": "55", "subject": "Quarterly Report", "from": "boss@corp.com", "date": "19 Oct 2026", "unread": True}
        ]
        res = execute_tool("search_emails", {"unread_only": True, "limit": 1})
        assert res.success is True
        assert "Quarterly Report" in res.message
        assert "[UNREAD]" in res.message
        assert "boss@corp.com" in res.message

    @patch("scout.mail.client.read_email")
    def test_tool_read_email(self, mock_read):
        mock_read.return_value = {
            "id": "55",
            "subject": "Quarterly Report",
            "from": "boss@corp.com",
            "to": "user@gmail.com",
            "date": "19 Oct 2026",
            "body": "Great progress this quarter. Keep it up!",
            "attachments": ["q3_report.pdf"],
        }
        res = execute_tool("read_email", {"email_id": "55"})
        assert res.success is True
        assert "Great progress this quarter" in res.message
        assert "q3_report.pdf" in res.message

    def test_email_acknowledgment(self):
        task = "Check my latest emails from boss"
        assert is_actionable_task(task) is True
        ack = generate_acknowledgment(task)
        assert ack is not None
        assert any(word in ack.lower() for word in ("email", "inbox"))
