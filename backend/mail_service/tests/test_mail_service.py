import asyncio
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

from backend.mail_service.mail_service import MailFetchResult, MailService
from backend.mail_service.models import IMAPConfig, ParsedEmail
from backend.mail_service.imap_connection import IMAPConnectionError


def _make_config(**kwargs) -> IMAPConfig:
    defaults = dict(
        host="imap.example.com",
        port=993,
        username="user@example.com",
        password="secret",
        use_ssl=True,
        mailbox="INBOX",
        max_emails=10,
    )
    defaults.update(kwargs)
    return IMAPConfig(**defaults)


def _make_raw_email(subject="Test", sender="a@b.com", body="hello") -> bytes:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"
    return msg.as_bytes()


def _make_mock_conn(uids: list[bytes], raw_messages: dict[bytes, bytes]):
    conn = MagicMock()
    conn.fetch_unread_uids.return_value = uids
    conn.fetch_raw_message.side_effect = lambda uid: raw_messages.get(uid)
    return conn


class TestMailFetchResult:
    def test_success_with_emails(self):
        result = MailFetchResult(emails=[MagicMock()], errors=[])
        assert result.success is True
        assert result.total_fetched == 1

    def test_success_with_no_emails_no_errors(self):
        result = MailFetchResult(emails=[], errors=[])
        assert result.success is True

    def test_failure_with_errors_no_emails(self):
        result = MailFetchResult(emails=[], errors=["connection failed"])
        assert result.success is False


class TestMailServiceFetch:
    @pytest.mark.asyncio
    async def test_fetches_unread_emails(self):
        config = _make_config()
        service = MailService(config)

        uid = b"1"
        raw = _make_raw_email(subject="Invoice #1", sender="vendor@co.com")
        mock_conn = _make_mock_conn([uid], {uid: raw})

        with patch("backend.mail_service.mail_service.imap_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = await service.fetch_unread()

        assert result.total_fetched == 1
        assert result.emails[0].subject == "Invoice #1"
        assert result.emails[0].sender == "vendor@co.com"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_unread(self):
        config = _make_config()
        service = MailService(config)

        mock_conn = _make_mock_conn([], {})

        with patch("backend.mail_service.mail_service.imap_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = await service.fetch_unread()

        assert result.total_fetched == 0
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_handles_connection_error(self):
        config = _make_config()
        service = MailService(config)

        with patch("backend.mail_service.mail_service.imap_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(
                side_effect=IMAPConnectionError("Connection refused")
            )
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = await service.fetch_unread()

        assert result.total_fetched == 0
        assert len(result.errors) > 0
        assert "Connection" in result.errors[0]

    @pytest.mark.asyncio
    async def test_respects_max_emails_limit(self):
        config = _make_config(max_emails=2)
        service = MailService(config)

        uids = [b"1", b"2", b"3", b"4", b"5"]
        raw = _make_raw_email()
        raw_messages = {uid: raw for uid in uids}
        mock_conn = _make_mock_conn(uids, raw_messages)

        with patch("backend.mail_service.mail_service.imap_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = await service.fetch_unread()

        assert result.total_fetched == 2

    @pytest.mark.asyncio
    async def test_records_error_on_empty_raw_message(self):
        config = _make_config()
        service = MailService(config)

        uid = b"99"
        mock_conn = _make_mock_conn([uid], {uid: None})

        with patch("backend.mail_service.mail_service.imap_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = await service.fetch_unread()

        assert result.total_fetched == 0
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_fetches_multiple_emails(self):
        config = _make_config(max_emails=50)
        service = MailService(config)

        uids = [b"1", b"2", b"3"]
        raw_messages = {
            b"1": _make_raw_email(subject="Invoice", sender="a@co.com"),
            b"2": _make_raw_email(subject="Meeting", sender="b@co.com"),
            b"3": _make_raw_email(subject="Spam offer", sender="c@co.com"),
        }
        mock_conn = _make_mock_conn(uids, raw_messages)

        with patch("backend.mail_service.mail_service.imap_session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            result = await service.fetch_unread()

        assert result.total_fetched == 3
        subjects = [e.subject for e in result.emails]
        assert "Invoice" in subjects
        assert "Meeting" in subjects
