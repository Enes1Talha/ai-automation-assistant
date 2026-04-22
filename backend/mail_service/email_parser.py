from __future__ import annotations

import email
import logging
import quopri
import re
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from typing import Optional

from backend.mail_service.models import Attachment, ParsedEmail

logger = logging.getLogger(__name__)

_BODY_MAX_CHARS = 1000
_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB hard limit per attachment

# MIME types we treat as plain text body candidates
_TEXT_TYPES = {"text/plain", "text/html"}


def _decode_mime_words(raw: str) -> str:
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _safe_decode(data: bytes, charset: Optional[str]) -> str:
    charsets = [charset, "utf-8", "latin-1", "cp1252"] if charset else ["utf-8", "latin-1", "cp1252"]
    for enc in charsets:
        if enc is None:
            continue
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("ascii", errors="replace")


def _extract_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset()
    text = _safe_decode(payload, charset)

    if part.get_content_type() == "text/html":
        # Strip HTML tags for plain-text body
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

    return text.strip()


def _parse_date(raw_date: Optional[str]) -> datetime:
    if not raw_date:
        return datetime.now(tz=timezone.utc)
    try:
        parsed = email.utils.parsedate_to_datetime(raw_date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.now(tz=timezone.utc)


def _parse_sender(raw: Optional[str]) -> str:
    if not raw:
        return "unknown"
    decoded = _decode_mime_words(raw)
    # Extract just the email address part
    match = re.search(r"<([^>]+)>", decoded)
    if match:
        return match.group(1).strip().lower()
    return decoded.strip().lower()


def _parse_attachments(msg: Message) -> list[Attachment]:
    attachments: list[Attachment] = []
    for part in msg.walk():
        disposition = part.get_content_disposition()
        content_type = part.get_content_type()

        # Skip multipart containers and text body parts
        if part.get_content_maintype() == "multipart":
            continue
        if disposition not in ("attachment", "inline") and content_type in _TEXT_TYPES:
            continue
        if disposition is None and content_type in _TEXT_TYPES:
            continue

        filename_raw = part.get_filename()
        if not filename_raw and disposition != "attachment":
            continue

        filename = _decode_mime_words(filename_raw or "unknown_file")
        filename = re.sub(r'[\\/:*?"<>|]', "_", filename)  # sanitize

        data = part.get_payload(decode=True)
        if not data:
            continue
        if len(data) > _MAX_ATTACHMENT_BYTES:
            logger.warning("Attachment %s too large (%d bytes), skipping", filename, len(data))
            continue

        attachments.append(
            Attachment(
                filename=filename,
                content_type=content_type,
                data=data,
            )
        )
    return attachments


class EmailParser:
    def __init__(self, body_max_chars: int = _BODY_MAX_CHARS) -> None:
        self._body_max_chars = body_max_chars

    def parse(self, uid: str, raw_message: bytes) -> Optional[ParsedEmail]:
        try:
            msg = email.message_from_bytes(raw_message)
            return self._parse_message(uid, msg, len(raw_message))
        except Exception as exc:
            logger.error("Failed to parse email uid=%s: %s", uid, exc)
            return None

    def _parse_message(self, uid: str, msg: Message, raw_size: int) -> ParsedEmail:
        subject = _decode_mime_words(msg.get("Subject") or "")
        sender = _parse_sender(msg.get("From"))
        date = _parse_date(msg.get("Date"))
        body = self._extract_body(msg)
        attachments = _parse_attachments(msg)

        return ParsedEmail(
            uid=uid,
            subject=subject,
            sender=sender,
            date=date,
            body=body[: self._body_max_chars],
            attachments=attachments,
            raw_size=raw_size,
        )

    def _extract_body(self, msg: Message) -> str:
        plain_parts: list[str] = []
        html_parts: list[str] = []

        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get_content_disposition() == "attachment":
                    continue
                if ct == "text/plain":
                    plain_parts.append(_extract_text(part))
                elif ct == "text/html":
                    html_parts.append(_extract_text(part))
        else:
            ct = msg.get_content_type()
            if ct == "text/plain":
                plain_parts.append(_extract_text(msg))
            elif ct == "text/html":
                html_parts.append(_extract_text(msg))

        # Prefer plain text; fall back to stripped HTML
        parts = plain_parts or html_parts
        return " ".join(p for p in parts if p).strip()
