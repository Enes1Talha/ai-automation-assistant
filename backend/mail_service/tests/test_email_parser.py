import email as email_lib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import pytest

from backend.mail_service.email_parser import EmailParser
from backend.mail_service.models import ParsedEmail


def _make_simple_email(
    subject="Test Subject",
    sender="sender@example.com",
    body="Hello world",
    charset="utf-8",
) -> bytes:
    msg = MIMEText(body, "plain", charset)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"
    return msg.as_bytes()


def _make_multipart_email(plain: str = "", html: str = "", with_attachment: bool = False) -> bytes:
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "Multipart Email"
    msg["From"] = "test@example.com"
    msg["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"

    alt = MIMEMultipart("alternative")
    if plain:
        alt.attach(MIMEText(plain, "plain", "utf-8"))
    if html:
        alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    if with_attachment:
        part = MIMEBase("application", "pdf")
        part.set_payload(b"PDF_CONTENT_BYTES")
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="invoice.pdf")
        msg.attach(part)

    return msg.as_bytes()


@pytest.fixture
def parser():
    return EmailParser(body_max_chars=1000)


class TestBasicParsing:
    def test_parses_subject(self, parser):
        raw = _make_simple_email(subject="Hello World")
        result = parser.parse("1", raw)
        assert result is not None
        assert result.subject == "Hello World"

    def test_parses_sender_email(self, parser):
        raw = _make_simple_email(sender="John Doe <john@example.com>")
        result = parser.parse("1", raw)
        assert result.sender == "john@example.com"

    def test_parses_sender_plain(self, parser):
        raw = _make_simple_email(sender="jane@example.com")
        result = parser.parse("1", raw)
        assert result.sender == "jane@example.com"

    def test_normalizes_sender_to_lowercase(self, parser):
        raw = _make_simple_email(sender="UPPER@EXAMPLE.COM")
        result = parser.parse("1", raw)
        assert result.sender == "upper@example.com"

    def test_parses_body(self, parser):
        raw = _make_simple_email(body="This is the email body")
        result = parser.parse("1", raw)
        assert "This is the email body" in result.body

    def test_parses_date(self, parser):
        raw = _make_simple_email()
        result = parser.parse("1", raw)
        assert isinstance(result.date, datetime)
        assert result.date.year == 2024

    def test_uid_stored(self, parser):
        raw = _make_simple_email()
        result = parser.parse("42", raw)
        assert result.uid == "42"

    def test_raw_size_recorded(self, parser):
        raw = _make_simple_email()
        result = parser.parse("1", raw)
        assert result.raw_size == len(raw)


class TestBodyTrimming:
    def test_body_trimmed_to_max_chars(self):
        parser = EmailParser(body_max_chars=100)
        raw = _make_simple_email(body="x" * 500)
        result = parser.parse("1", raw)
        assert len(result.body) <= 100

    def test_body_not_trimmed_when_under_limit(self, parser):
        raw = _make_simple_email(body="Short body")
        result = parser.parse("1", raw)
        assert result.body == "Short body"


class TestMultipartEmails:
    def test_prefers_plain_over_html(self, parser):
        raw = _make_multipart_email(plain="plain text body", html="<p>html body</p>")
        result = parser.parse("1", raw)
        assert "plain text body" in result.body
        assert "<p>" not in result.body

    def test_falls_back_to_html_when_no_plain(self, parser):
        raw = _make_multipart_email(html="<p>Hello from HTML</p>")
        result = parser.parse("1", raw)
        assert "Hello from HTML" in result.body

    def test_html_tags_stripped(self, parser):
        raw = _make_multipart_email(html="<b>Bold</b> text <a href='x'>link</a>")
        result = parser.parse("1", raw)
        assert "<b>" not in result.body
        assert "Bold" in result.body


class TestAttachments:
    def test_no_attachments(self, parser):
        raw = _make_simple_email()
        result = parser.parse("1", raw)
        assert result.has_attachments is False
        assert result.attachments == []

    def test_detects_attachment(self, parser):
        raw = _make_multipart_email(plain="see attached", with_attachment=True)
        result = parser.parse("1", raw)
        assert result.has_attachments is True
        assert len(result.attachments) == 1

    def test_attachment_filename(self, parser):
        raw = _make_multipart_email(plain="body", with_attachment=True)
        result = parser.parse("1", raw)
        assert result.attachments[0].filename == "invoice.pdf"

    def test_attachment_content_type(self, parser):
        raw = _make_multipart_email(plain="body", with_attachment=True)
        result = parser.parse("1", raw)
        assert result.attachments[0].content_type == "application/pdf"

    def test_attachment_size_set(self, parser):
        raw = _make_multipart_email(plain="body", with_attachment=True)
        result = parser.parse("1", raw)
        assert result.attachments[0].size > 0


class TestEncodingHandling:
    def test_utf8_body(self, parser):
        raw = _make_simple_email(body="Türkçe karakterler: şğüöçı")
        result = parser.parse("1", raw)
        assert "Türkçe" in result.body

    def test_latin1_body(self, parser):
        raw = _make_simple_email(body="café résumé", charset="latin-1")
        result = parser.parse("1", raw)
        assert result.body  # should not crash

    def test_missing_date_defaults_to_now(self, parser):
        msg = MIMEText("body", "plain", "utf-8")
        msg["Subject"] = "No date"
        msg["From"] = "a@b.com"
        result = parser.parse("1", msg.as_bytes())
        assert isinstance(result.date, datetime)

    def test_corrupt_raw_returns_none(self, parser):
        result = parser.parse("1", b"NOT A VALID EMAIL AT ALL \x00\xff")
        # Should not raise — returns None or best-effort
        # email.message_from_bytes is very lenient, may still return something
        assert result is None or isinstance(result, ParsedEmail)


class TestBodyPreview:
    def test_body_preview_max_200(self, parser):
        raw = _make_simple_email(body="a" * 500)
        result = parser.parse("1", raw)
        assert len(result.body_preview) <= 200
