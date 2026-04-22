from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.database import Base
from backend.database.models import MailRecord
from backend.mail_service.models import Attachment, ParsedEmail
from backend.mail_service.mail_service import MailFetchResult
from backend.models.email_models import (
    ClassificationResponse,
    ClassificationResult,
    EmailCategory,
)
from backend.api.services.pipeline_service import PipelineService

# ── In-memory DB ──────────────────────────────────────────────────────────────
engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def _make_parsed_email(uid="1", subject="Invoice", sender="a@b.com", body="pay now") -> ParsedEmail:
    return ParsedEmail(
        uid=uid,
        subject=subject,
        sender=sender,
        date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        body=body,
        attachments=[],
        raw_size=512,
    )


def _make_classification(category=EmailCategory.INVOICE, confidence=0.9) -> ClassificationResult:
    return ClassificationResult(
        category=category,
        confidence=confidence,
        reason="test",
        source="ai",
    )


def _make_pipeline(emails: list[ParsedEmail], classification: ClassificationResult) -> PipelineService:
    mail_svc = MagicMock()
    mail_svc.fetch_unread = AsyncMock(return_value=MailFetchResult(emails=emails, errors=[]))

    classifier_svc = MagicMock()
    classifier_svc.classify = AsyncMock(
        return_value=ClassificationResponse(success=True, result=classification)
    )

    return PipelineService(mail_svc, classifier_svc)


class TestPipelineRun:
    @pytest.mark.asyncio
    async def test_saves_email_to_db(self, db):
        email = _make_parsed_email(uid="42", subject="Invoice #1")
        pipeline = _make_pipeline([email], _make_classification())

        result = await pipeline.run(db)

        assert result["processed"] == 1
        record = db.query(MailRecord).filter(MailRecord.uid == "42").first()
        assert record is not None
        assert record.subject == "Invoice #1"
        assert record.category == "invoice"

    @pytest.mark.asyncio
    async def test_skips_duplicate_uid(self, db):
        email = _make_parsed_email(uid="99")
        pipeline = _make_pipeline([email], _make_classification())

        await pipeline.run(db)
        result = await pipeline.run(db)

        assert result["processed"] == 0
        count = db.query(MailRecord).filter(MailRecord.uid == "99").count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_records_confidence_and_source(self, db):
        email = _make_parsed_email()
        classification = _make_classification(category=EmailCategory.SPAM, confidence=0.75)
        pipeline = _make_pipeline([email], classification)

        await pipeline.run(db)

        record = db.query(MailRecord).first()
        assert record.category == "spam"
        assert abs(record.confidence - 0.75) < 0.001
        assert record.classification_source == "ai"

    @pytest.mark.asyncio
    async def test_handles_fetch_errors(self, db):
        mail_svc = MagicMock()
        mail_svc.fetch_unread = AsyncMock(
            return_value=MailFetchResult(emails=[], errors=["Connection refused"])
        )
        classifier_svc = MagicMock()
        pipeline = PipelineService(mail_svc, classifier_svc)

        result = await pipeline.run(db)

        assert result["processed"] == 0
        assert "Connection refused" in result["errors"]

    @pytest.mark.asyncio
    async def test_processes_multiple_emails(self, db):
        emails = [
            _make_parsed_email(uid="1", subject="Invoice"),
            _make_parsed_email(uid="2", subject="Meeting"),
            _make_parsed_email(uid="3", subject="Spam offer"),
        ]
        pipeline = _make_pipeline(emails, _make_classification())

        result = await pipeline.run(db)

        assert result["processed"] == 3
        assert db.query(MailRecord).count() == 3

    @pytest.mark.asyncio
    async def test_attachment_info_stored(self, db):
        email = _make_parsed_email()
        email.attachments = [
            Attachment(filename="file.pdf", content_type="application/pdf", data=b"PDF")
        ]
        pipeline = _make_pipeline([email], _make_classification())

        await pipeline.run(db)

        record = db.query(MailRecord).first()
        assert record.has_attachments is True
        assert record.attachment_count == 1
