from __future__ import annotations

import logging
import os
from typing import Optional
from sqlalchemy.orm import Session

from backend.mail_service.mail_service import MailService, make_mail_service
from backend.mail_service.models import ParsedEmail
from backend.ai_service.classification_service import ClassificationService
from backend.models.email_models import ClassificationResult, EmailInput, ClassificationRequest
from backend.database.models import MailRecord
from backend.automation_service.automation_service import AutomationService, make_automation_service

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Full pipeline: fetch emails → classify → automate (save files + Excel) → persist DB.
    """

    def __init__(
        self,
        mail_service: MailService,
        classification_service: ClassificationService,
        automation_service: Optional[AutomationService] = None,
    ) -> None:
        self._mail = mail_service
        self._classifier = classification_service
        self._automation = automation_service

    async def run(self, db: Session) -> dict:
        errors: list[str] = []
        saved = 0

        fetch_result = await self._mail.fetch_unread()
        errors.extend(fetch_result.errors)

        for parsed_email in fetch_result.emails:
            try:
                record = await self._process_one(parsed_email, db)
                if record:
                    saved += 1
            except Exception as exc:
                msg = f"Pipeline error for uid={parsed_email.uid}: {exc}"
                logger.error(msg)
                errors.append(msg)

        return {"processed": saved, "errors": errors}

    async def _process_one(self, email: ParsedEmail, db: Session) -> MailRecord | None:
        existing = db.query(MailRecord).filter(MailRecord.uid == email.uid).first()
        if existing:
            logger.debug("Skipping already-processed uid=%s", email.uid)
            return None

        classification = await self._classify(email)

        # Automation: save attachments + write Excel
        if self._automation is not None:
            try:
                auto_result = self._automation.process(email, classification)
                if auto_result.errors:
                    logger.warning("Automation warnings for uid=%s: %s", email.uid, auto_result.errors)
            except Exception as exc:
                logger.error("Automation failed for uid=%s: %s", email.uid, exc)

        record = MailRecord(
            uid=email.uid,
            subject=email.subject,
            sender=email.sender,
            body_preview=email.body_preview,
            category=classification.category.value,
            confidence=classification.confidence,
            classification_reason=classification.reason,
            classification_source=classification.source,
            has_attachments=email.has_attachments,
            attachment_count=len(email.attachments),
            raw_size=email.raw_size,
            email_date=email.date,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(
            "Processed uid=%s category=%s confidence=%.2f source=%s",
            email.uid, classification.category, classification.confidence, classification.source,
        )
        return record

    async def _classify(self, email: ParsedEmail) -> ClassificationResult:
        request = ClassificationRequest(
            email=EmailInput(subject=email.subject, sender=email.sender, body=email.body)
        )
        response = await self._classifier.classify(request)
        if not response.success or response.result is None:
            raise RuntimeError(f"Classification failed: {response.error}")
        return response.result


def make_pipeline_service() -> PipelineService:
    mail_svc = make_mail_service(
        host=os.environ.get("IMAP_HOST", "imap.gmail.com"),
        port=int(os.environ.get("IMAP_PORT", "993")),
        username=os.environ.get("IMAP_USERNAME", ""),
        password=os.environ.get("IMAP_PASSWORD", ""),
        use_ssl=os.environ.get("IMAP_SSL", "true").lower() == "true",
        mailbox=os.environ.get("IMAP_MAILBOX", "INBOX"),
        max_emails=int(os.environ.get("MAX_EMAILS_PER_RUN", "50")),
    )
    classifier_svc = ClassificationService(
        confidence_threshold=float(os.environ.get("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")),
    )
    automation_svc = make_automation_service(
        base_dir=os.environ.get("STORAGE_BASE_DIR", "storage"),
    )
    return PipelineService(mail_svc, classifier_svc, automation_svc)
