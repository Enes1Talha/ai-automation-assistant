from __future__ import annotations

import os
from pathlib import Path

from backend.agent.agent import MailAgent
from backend.agent.tools.executor import ToolExecutor
from backend.ai_service.classification_service import ClassificationService
from backend.ai_service.order_extractor import OrderExtractorService
from backend.automation_service.excel_reporter import ExcelReporter
from backend.automation_service.storage_service import StorageService


def make_mail_agent(
    base_dir: str | Path = "storage",
    api_key: str | None = None,
) -> MailAgent:
    base = Path(base_dir)
    classifier = ClassificationService(
        confidence_threshold=float(os.environ.get("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6"))
    )
    storage = StorageService(base_dir=base)
    reporter = ExcelReporter(report_path=base / "report.xlsx")
    order_extractor = OrderExtractorService(api_key=api_key)
    executor = ToolExecutor(
        classifier=classifier,
        storage=storage,
        reporter=reporter,
        order_extractor=order_extractor,
    )
    return MailAgent(executor=executor, api_key=api_key)
