from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.automation_service.excel_reporter import ExcelReporter, ReportRow
from backend.automation_service.storage_service import SavedFile, StorageService
from backend.mail_service.models import Attachment, ParsedEmail
from backend.models.email_models import ClassificationResult

logger = logging.getLogger(__name__)


@dataclass
class AutomationResult:
    email_uid: str
    category: str
    files_saved: list[SavedFile] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    excel_written: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class AutomationService:
    """
    Processes a classified email:
      1. Save each attachment to its categorized folder
      2. Append a record to the Excel report
    Cleanly separated from AI/mail logic.
    """

    def __init__(
        self,
        storage: StorageService,
        reporter: ExcelReporter,
    ) -> None:
        self._storage = storage
        self._reporter = reporter

    def process(
        self,
        email: ParsedEmail,
        classification: ClassificationResult,
    ) -> AutomationResult:
        category = classification.category.value
        result = AutomationResult(email_uid=email.uid, category=category)

        # 1. Save attachments
        if email.attachments:
            storage_result = self._storage.save_attachments(
                attachments=[(a.filename, a.data) for a in email.attachments],
                category=category,
                sender=email.sender,
                email_date=email.date,
            )
            result.files_saved = storage_result.saved
            result.files_skipped = storage_result.skipped
            result.errors.extend(storage_result.errors)

        # 2. Build file_path summary for the report
        file_paths = ", ".join(str(f.saved_path) for f in result.files_saved) if result.files_saved else ""

        # 3. Append to Excel
        row = ReportRow(
            date=email.date.strftime("%Y-%m-%d %H:%M:%S"),
            sender=email.sender,
            subject=email.subject,
            category=category,
            confidence=classification.confidence,
            file_path=file_paths,
            has_attachments=email.has_attachments,
        )
        try:
            result.excel_written = self._reporter.append(row)
        except Exception as exc:
            msg = f"Excel write failed: {exc}"
            logger.error(msg)
            result.errors.append(msg)

        return result

    def process_batch(
        self,
        emails: list[tuple[ParsedEmail, ClassificationResult]],
    ) -> list[AutomationResult]:
        return [self.process(email, classification) for email, classification in emails]


def make_automation_service(
    base_dir: str | Path = "storage",
    report_path: Optional[str | Path] = None,
) -> AutomationService:
    storage = StorageService(base_dir=base_dir)
    reporter = ExcelReporter(report_path or Path(base_dir) / "report.xlsx")
    return AutomationService(storage=storage, reporter=reporter)
