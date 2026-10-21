"""Gmail IMAP client integration for Scout."""

from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
import os
import re
from typing import Any, Optional

from bs4 import BeautifulSoup
from rich.console import Console

from scout.core.auth import get_api_key, set_api_key, delete_api_key
from scout.user_config import load_config, save_config

console = Console()

GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993


def get_email_credentials() -> tuple[Optional[str], Optional[str]]:
    """Retrieve configured Gmail address and App Password.
    
    Checks:
    1. config.json -> email.address
    2. Keyring (Windows Credential Manager) -> gmail
    3. config.json -> email.app_password (fallback)
    4. Environment variables: GMAIL_ADDRESS, GMAIL_APP_PASSWORD
    """
    config = load_config()
    email_cfg = config.get("email", {})

    address = email_cfg.get("address") or os.environ.get("GMAIL_ADDRESS")
    
    # App Password from secure keyring first
    app_password = get_api_key("gmail")
    if not app_password:
        app_password = email_cfg.get("app_password") or os.environ.get("GMAIL_APP_PASSWORD")

    if address:
        address = address.strip()
    if app_password:
        app_password = app_password.strip().replace(" ", "")

    return address, app_password


def save_email_credentials(address: str, app_password: str) -> None:
    """Save Gmail address to config and App Password securely to Windows Credential Manager."""
    clean_address = address.strip()
    clean_pwd = app_password.strip().replace(" ", "")

    # Store password in secure OS keyring
    try:
        set_api_key("gmail", clean_pwd)
    except Exception:
        pass

    # Store email address in config.json
    config = load_config()
    if "email" not in config:
        config["email"] = {}
    config["email"]["address"] = clean_address
    config["email"]["provider"] = "gmail"
    save_config(config)


def clear_email_credentials() -> None:
    """Remove stored email credentials from config and keyring."""
    try:
        delete_api_key("gmail")
    except Exception:
        pass

    config = load_config()
    if "email" in config:
        del config["email"]
        save_config(config)


def _connect_imap() -> imaplib.IMAP4_SSL:
    """Establish authenticated IMAP SSL connection to Gmail."""
    address, app_password = get_email_credentials()
    if not address or not app_password:
        raise ValueError(
            "Gmail credentials not configured. Please run '/email setup' to configure "
            "your Gmail address and 16-character Google App Password."
        )

    mail = imaplib.IMAP4_SSL(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
    try:
        mail.login(address, app_password)
    except imaplib.IMAP4.error as e:
        mail.logout()
        raise PermissionError(
            f"Gmail authentication failed: {e}. Ensure you are using a 16-character Google App Password "
            f"(generated at https://myaccount.google.com/apppasswords), NOT your normal Google account password."
        )
    return mail


def test_connection() -> tuple[bool, str]:
    """Test connection and authentication to Gmail IMAP."""
    try:
        mail = _connect_imap()
        mail.select("INBOX", readonly=True)
        mail.close()
        mail.logout()
        addr, _ = get_email_credentials()
        return True, f"Successfully authenticated to Gmail as {addr}."
    except Exception as e:
        return False, str(e)


def _decode_header_str(val: Optional[str]) -> str:
    """Safely decode RFC 2047 MIME encoded header values."""
    if not val:
        return ""
    try:
        parts = []
        for text, charset in email.header.decode_header(val):
            if isinstance(text, bytes):
                parts.append(text.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(str(text))
        return "".join(parts).strip()
    except Exception:
        return str(val).strip()


def _html_to_clean_text(html: str) -> str:
    """Convert HTML email body into clean, readable text."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "meta", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    except Exception:
        return re.sub(r"<[^>]+>", "", html).strip()


def search_emails(
    query: Optional[str] = None,
    unread_only: bool = False,
    sender: Optional[str] = None,
    subject: Optional[str] = None,
    limit: int = 5,
    folder: str = "INBOX",
) -> list[dict[str, Any]]:
    """Search emails in Gmail folder and return metadata summaries."""
    mail = _connect_imap()
    try:
        res, _ = mail.select(folder, readonly=True)
        if res != "OK":
            raise ValueError(f"Could not open folder '{folder}'.")

        # Build IMAP search criteria
        criteria: list[str] = []
        if unread_only:
            criteria.append("UNSEEN")
        if sender:
            clean_s = sender.strip().replace('"', "")
            criteria.append(f'FROM "{clean_s}"')
        if subject:
            clean_sub = subject.strip().replace('"', "")
            criteria.append(f'SUBJECT "{clean_sub}"')
        if query:
            clean_q = query.strip().replace('"', "")
            criteria.append(f'TEXT "{clean_q}"')

        search_cmd = " ".join(criteria) if criteria else "ALL"
        status, data = mail.search(None, search_cmd)
        if status != "OK" or not data or not data[0]:
            return []

        msg_ids = data[0].split()
        # Newest messages first
        recent_ids = msg_ids[-max(1, limit):]
        recent_ids.reverse()

        results: list[dict[str, Any]] = []
        for mid in recent_ids:
            mid_str = mid.decode("utf-8")
            status, fetch_data = mail.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE TO)] FLAGS)")
            if status != "OK" or not fetch_data:
                continue

            msg_bytes = None
            flags_str = ""
            for item in fetch_data:
                if isinstance(item, tuple) and len(item) == 2:
                    msg_bytes = item[1]
                elif isinstance(item, bytes):
                    flags_str = item.decode("utf-8", errors="replace")

            if not msg_bytes:
                continue

            msg = email.message_from_bytes(msg_bytes)
            sub = _decode_header_str(msg.get("Subject", "(No Subject)"))
            from_hdr = _decode_header_str(msg.get("From", "(Unknown Sender)"))
            date_hdr = _decode_header_str(msg.get("Date", ""))
            is_unread = "\\Seen" not in flags_str

            results.append({
                "id": mid_str,
                "subject": sub,
                "from": from_hdr,
                "date": date_hdr,
                "unread": is_unread,
            })

        return results
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


def read_email(email_id: str, folder: str = "INBOX") -> dict[str, Any]:
    """Retrieve the full content, headers, and attachments list for a specific email."""
    mail = _connect_imap()
    try:
        res, _ = mail.select(folder, readonly=True)
        if res != "OK":
            raise ValueError(f"Could not open folder '{folder}'.")

        status, data = mail.fetch(email_id.encode("utf-8"), "(BODY.PEEK[])")
        if status != "OK" or not data or not data[0]:
            raise ValueError(f"Email with ID '{email_id}' not found.")

        raw_bytes = None
        for item in data:
            if isinstance(item, tuple) and len(item) == 2:
                raw_bytes = item[1]
                break

        if not raw_bytes:
            raise ValueError(f"Could not read content for email ID '{email_id}'.")

        msg = email.message_from_bytes(raw_bytes)
        sub = _decode_header_str(msg.get("Subject", "(No Subject)"))
        from_hdr = _decode_header_str(msg.get("From", "(Unknown Sender)"))
        to_hdr = _decode_header_str(msg.get("To", ""))
        date_hdr = _decode_header_str(msg.get("Date", ""))

        text_parts: list[str] = []
        html_parts: list[str] = []
        attachments: list[str] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                filename = part.get_filename()

                if filename:
                    attachments.append(_decode_header_str(filename))
                    continue

                if "attachment" in content_disposition:
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                charset = part.get_content_charset() or "utf-8"
                decoded_str = payload.decode(charset, errors="replace")

                if content_type == "text/plain":
                    text_parts.append(decoded_str)
                elif content_type == "text/html":
                    html_parts.append(decoded_str)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                decoded_str = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    html_parts.append(decoded_str)
                else:
                    text_parts.append(decoded_str)

        # Body: prefer text/plain, fallback to converted HTML
        if text_parts:
            body = "\n".join(text_parts).strip()
        elif html_parts:
            body = _html_to_clean_text("\n".join(html_parts))
        else:
            body = "(Empty email body)"

        return {
            "id": email_id,
            "subject": sub,
            "from": from_hdr,
            "to": to_hdr,
            "date": date_hdr,
            "body": body,
            "attachments": attachments,
        }
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass
