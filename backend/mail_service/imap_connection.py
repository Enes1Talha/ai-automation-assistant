from __future__ import annotations

import imaplib
import logging
import socket
from contextlib import contextmanager
from typing import Generator

from backend.mail_service.models import IMAPConfig

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30


class IMAPConnectionError(Exception):
    pass


class IMAPConnection:
    """Manages a single IMAP connection with automatic cleanup."""

    def __init__(self, config: IMAPConfig) -> None:
        self._config = config
        self._client: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        cfg = self._config
        try:
            socket.setdefaulttimeout(_TIMEOUT_SECONDS)
            if cfg.use_ssl:
                self._client = imaplib.IMAP4_SSL(cfg.host, cfg.port)
            else:
                self._client = imaplib.IMAP4(cfg.host, cfg.port)

            self._client.login(cfg.username, cfg.password)
            status, _ = self._client.select(cfg.mailbox, readonly=False)
            if status != "OK":
                raise IMAPConnectionError(f"Cannot select mailbox: {cfg.mailbox}")

            logger.info("Connected to %s as %s", cfg.host, cfg.username)
        except imaplib.IMAP4.error as exc:
            raise IMAPConnectionError(f"IMAP auth failed: {exc}") from exc
        except (socket.gaierror, socket.timeout, OSError) as exc:
            raise IMAPConnectionError(f"Network error connecting to {cfg.host}: {exc}") from exc

    def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            self._client.close()
            self._client.logout()
        except Exception:
            pass
        finally:
            self._client = None
            logger.info("Disconnected from IMAP server")

    @property
    def client(self) -> imaplib.IMAP4 | imaplib.IMAP4_SSL:
        if self._client is None:
            raise IMAPConnectionError("Not connected — call connect() first")
        return self._client

    def fetch_unread_uids(self) -> list[bytes]:
        status, data = self.client.search(None, "UNSEEN")
        if status != "OK" or not data or not data[0]:
            return []
        return data[0].split()

    def fetch_raw_message(self, uid: bytes) -> bytes | None:
        status, data = self.client.fetch(uid, "(RFC822)")
        if status != "OK" or not data or data[0] is None:
            return None
        raw = data[0]
        if isinstance(raw, tuple):
            return raw[1]
        return None

    def mark_as_read(self, uid: bytes) -> None:
        self.client.store(uid, "+FLAGS", "\\Seen")


@contextmanager
def imap_session(config: IMAPConfig) -> Generator[IMAPConnection, None, None]:
    conn = IMAPConnection(config)
    conn.connect()
    try:
        yield conn
    finally:
        conn.disconnect()
