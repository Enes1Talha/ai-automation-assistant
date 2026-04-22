from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from backend.mail_service.email_parser import EmailParser
from backend.mail_service.imap_connection import IMAPConnectionError, imap_session
from backend.mail_service.models import IMAPConfig, ParsedEmail

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mail_fetch")


class MailFetchResult:
    def __init__(self, emails: list[ParsedEmail], errors: list[str]) -> None:
        self.emails = emails
        self.errors = errors
        self.total_fetched = len(emails)

    @property
    def success(self) -> bool:
        return len(self.emails) > 0 or len(self.errors) == 0


class MailService:
    """
    Fetches and parses unread emails via IMAP.

    Runs IMAP I/O in a thread pool to keep the async event loop free.
    """

    def __init__(self, config: IMAPConfig) -> None:
        self._config = config
        self._parser = EmailParser(body_max_chars=config.body_max_chars)

    async def fetch_unread(self) -> MailFetchResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_EXECUTOR, self._fetch_unread_sync)

    def _fetch_unread_sync(self) -> MailFetchResult:
        emails: list[ParsedEmail] = []
        errors: list[str] = []

        try:
            with imap_session(self._config) as conn:
                uids = conn.fetch_unread_uids()
                if not uids:
                    logger.info("No unread emails found in %s", self._config.mailbox)
                    return MailFetchResult([], [])

                # Respect max_emails limit
                uids = uids[: self._config.max_emails]
                logger.info("Fetching %d unread email(s)", len(uids))

                for uid in uids:
                    try:
                        raw = conn.fetch_raw_message(uid)
                        if raw is None:
                            errors.append(f"Empty response for uid={uid!r}")
                            continue

                        parsed = self._parser.parse(uid=uid.decode(), raw_message=raw)
                        if parsed is None:
                            errors.append(f"Parse failed for uid={uid!r}")
                            continue

                        emails.append(parsed)
                        logger.debug(
                            "Parsed email uid=%s from=%s subject=%r",
                            uid.decode(),
                            parsed.sender,
                            parsed.subject[:50],
                        )
                    except Exception as exc:
                        errors.append(f"Error processing uid={uid!r}: {exc}")
                        logger.warning("Error processing email uid=%s: %s", uid, exc)

        except IMAPConnectionError as exc:
            errors.append(f"Connection error: {exc}")
            logger.error("IMAP connection error: %s", exc)

        return MailFetchResult(emails=emails, errors=errors)

    async def fetch_batch(self, batch_size: int = 10) -> list[MailFetchResult]:
        """Fetch emails in batches — useful for large inboxes."""
        original_max = self._config.max_emails
        results: list[MailFetchResult] = []
        offset = 0

        while offset < original_max:
            self._config.max_emails = min(batch_size, original_max - offset)
            result = await self.fetch_unread()
            results.append(result)

            if len(result.emails) < batch_size:
                break
            offset += batch_size

        self._config.max_emails = original_max
        return results


def make_mail_service(
    host: str,
    port: int,
    username: str,
    password: str,
    use_ssl: bool = True,
    mailbox: str = "INBOX",
    max_emails: int = 50,
) -> MailService:
    config = IMAPConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        use_ssl=use_ssl,
        mailbox=mailbox,
        max_emails=max_emails,
    )
    return MailService(config)
