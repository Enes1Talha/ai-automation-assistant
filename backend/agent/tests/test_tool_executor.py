import base64
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from backend.agent.tools.executor import ToolExecutor, ToolResult
from backend.automation_service.excel_reporter import ExcelReporter
from backend.automation_service.storage_service import StorageService
from backend.ai_service.classification_service import ClassificationService
from backend.models.email_models import (
    ClassificationResponse, ClassificationResult, EmailCategory,
)


def _make_executor(tmp_path: Path) -> ToolExecutor:
    classifier = MagicMock(spec=ClassificationService)
    storage = StorageService(base_dir=tmp_path)
    reporter = ExcelReporter(report_path=tmp_path / "report.xlsx")
    return ToolExecutor(classifier=classifier, storage=storage, reporter=reporter)


def _mock_classification(category=EmailCategory.INVOICE, confidence=0.9) -> ClassificationResponse:
    return ClassificationResponse(
        success=True,
        result=ClassificationResult(
            category=category, confidence=confidence,
            reason="test", source="ai",
        ),
    )


# ── classify_email ────────────────────────────────────────────────────────────

class TestClassifyEmailTool:
    @pytest.mark.asyncio
    async def test_returns_category_and_confidence(self, tmp_path):
        executor = _make_executor(tmp_path)
        executor._classifier.classify = AsyncMock(
            return_value=_mock_classification(EmailCategory.INVOICE, 0.95)
        )
        result = await executor.execute("classify_email", {
            "subject": "Invoice #42", "sender": "a@b.com", "body": "Please pay"
        })
        assert result.success is True
        assert result.output["category"] == "invoice"
        assert result.output["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_failed_classification_returns_error(self, tmp_path):
        executor = _make_executor(tmp_path)
        executor._classifier.classify = AsyncMock(
            return_value=ClassificationResponse(success=False, error="API down")
        )
        result = await executor.execute("classify_email", {
            "subject": "x", "sender": "x", "body": "x"
        })
        assert result.success is False
        assert result.error == "API down"


# ── download_attachment ───────────────────────────────────────────────────────

class TestDownloadAttachmentTool:
    @pytest.mark.asyncio
    async def test_decodes_base64_and_caches(self, tmp_path):
        executor = _make_executor(tmp_path)
        data = b"PDF binary data"
        b64 = base64.b64encode(data).decode()
        result = await executor.execute("download_attachment", {
            "filename": "doc.pdf", "content_b64": b64
        })
        assert result.success is True
        assert result.output["size_bytes"] == len(data)
        assert executor._attachment_cache["doc.pdf"] == data

    @pytest.mark.asyncio
    async def test_invalid_base64_returns_error(self, tmp_path):
        executor = _make_executor(tmp_path)
        result = await executor.execute("download_attachment", {
            "filename": "bad.pdf", "content_b64": "!!!not_b64!!!"
        })
        assert result.success is False
        assert "Base64" in result.error


# ── move_file ─────────────────────────────────────────────────────────────────

class TestMoveFileTool:
    @pytest.mark.asyncio
    async def test_moves_cached_file_to_folder(self, tmp_path):
        executor = _make_executor(tmp_path)
        executor._attachment_cache["invoice.pdf"] = b"PDF_DATA"
        result = await executor.execute("move_file", {
            "filename": "invoice.pdf", "content_b64": "", "category": "invoice"
        })
        assert result.success is True
        assert (tmp_path / "invoices" / "invoice.pdf").exists()

    @pytest.mark.asyncio
    async def test_moves_file_via_b64_without_cache(self, tmp_path):
        executor = _make_executor(tmp_path)
        b64 = base64.b64encode(b"SPAM_DATA").decode()
        result = await executor.execute("move_file", {
            "filename": "ad.jpg", "content_b64": b64, "category": "spam"
        })
        assert result.success is True
        assert "spam" in result.output["saved_path"]

    @pytest.mark.asyncio
    async def test_no_data_returns_error(self, tmp_path):
        executor = _make_executor(tmp_path)
        result = await executor.execute("move_file", {
            "filename": "x.pdf", "content_b64": "", "category": "other"
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_duplicate_returns_skipped(self, tmp_path):
        executor = _make_executor(tmp_path)
        executor._attachment_cache["dup.pdf"] = b"SAME"
        await executor.execute("move_file", {"filename": "dup.pdf", "content_b64": "", "category": "invoice"})
        # Second call — same file
        executor._attachment_cache["dup.pdf"] = b"SAME"
        result = await executor.execute("move_file", {"filename": "dup.pdf", "content_b64": "", "category": "invoice"})
        assert result.output.get("skipped") is True


# ── save_to_excel ─────────────────────────────────────────────────────────────

class TestSaveToExcelTool:
    @pytest.mark.asyncio
    async def test_writes_row_and_returns_true(self, tmp_path):
        executor = _make_executor(tmp_path)
        result = await executor.execute("save_to_excel", {
            "date": "2024-01-01 10:00:00",
            "sender": "v@co.com",
            "subject": "Invoice #1",
            "category": "invoice",
            "confidence": 0.92,
            "file_path": "/storage/invoices/doc.pdf",
            "has_attachments": True,
        })
        assert result.success is True
        assert result.output["written"] is True

    @pytest.mark.asyncio
    async def test_duplicate_row_skipped(self, tmp_path):
        executor = _make_executor(tmp_path)
        inp = {
            "date": "2024-01-01 10:00:00", "sender": "a@b.com", "subject": "X",
            "category": "spam", "confidence": 0.8, "file_path": "", "has_attachments": False,
        }
        await executor.execute("save_to_excel", inp)
        result = await executor.execute("save_to_excel", inp)
        assert result.output["skipped_duplicate"] is True


# ── unknown tool ──────────────────────────────────────────────────────────────

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, tmp_path):
        executor = _make_executor(tmp_path)
        result = await executor.execute("does_not_exist", {})
        assert result.success is False
        assert "Unknown tool" in result.error
