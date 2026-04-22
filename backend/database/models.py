from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.database import Base


class MailRecord(Base):
    __tablename__ = "mail_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(500), default="")
    sender: Mapped[str] = mapped_column(String(320), index=True)
    body_preview: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(50), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    classification_reason: Mapped[str] = mapped_column(String(300), default="")
    classification_source: Mapped[str] = mapped_column(String(20), default="ai")
    has_attachments: Mapped[bool] = mapped_column(default=False)
    attachment_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_size: Mapped[int] = mapped_column(Integer, default=0)
    email_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=timezone.utc),
    )
