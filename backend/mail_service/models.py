from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Attachment:
    filename: str
    content_type: str
    data: bytes
    size: int = field(init=False)

    def __post_init__(self) -> None:
        self.size = len(self.data)


@dataclass
class ParsedEmail:
    uid: str
    subject: str
    sender: str
    date: datetime
    body: str
    attachments: list[Attachment] = field(default_factory=list)
    raw_size: int = 0

    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0

    @property
    def body_preview(self) -> str:
        return self.body[:200]


@dataclass
class IMAPConfig:
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    mailbox: str = "INBOX"
    max_emails: int = 50
    body_max_chars: int = 1000
