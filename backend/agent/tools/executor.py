"""
Maps tool names → actual service calls.
Completely decoupled from the agent loop — easy to test independently.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any

from backend.ai_service.classification_service import ClassificationService
from backend.ai_service.fallback_classifier import FallbackClassifier
from backend.automation_service.excel_reporter import ExcelReporter, ReportRow
from backend.automation_service.storage_service import StorageService
from backend.models.email_models import ClassificationRequest, EmailInput

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: dict[str, Any]
    error: str | None = None

    def to_content(self) -> str:
        if self.error:
            return f"ERROR: {self.error}"
        import json
        return json.dumps(self.output, default=str)


class ToolExecutor:
    """Executes agent tool calls against real service instances."""

    def __init__(
        self,
        classifier: ClassificationService,
        storage: StorageService,
        reporter: ExcelReporter,
    ) -> None:
        self._classifier = classifier
        self._storage = storage
        self._reporter = reporter
        # Internal attachment cache: filename → bytes (within one agent run)
        self._attachment_cache: dict[str, bytes] = {}

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        handlers = {
            "classify_email":      self._classify_email,
            "download_attachment": self._download_attachment,
            "save_to_excel":       self._save_to_excel,
            "move_file":           self._move_file,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return ToolResult(tool_name=tool_name, success=False, output={},
                              error=f"Unknown tool: {tool_name!r}")
        try:
            return await handler(tool_input)
        except Exception as exc:
            logger.error("Tool %s failed: %s", tool_name, exc)
            return ToolResult(tool_name=tool_name, success=False, output={}, error=str(exc))

    # ── Tool handlers ─────────────────────────────────────────────────────────

    async def _classify_email(self, inp: dict) -> ToolResult:
        request = ClassificationRequest(
            email=EmailInput(
                subject=inp.get("subject", ""),
                sender=inp.get("sender", ""),
                body=inp.get("body", ""),
            )
        )
        response = await self._classifier.classify(request)
        if not response.success or response.result is None:
            return ToolResult("classify_email", False, {}, error=response.error)

        result = response.result
        return ToolResult("classify_email", True, {
            "category":   result.category.value,
            "confidence": round(result.confidence, 4),
            "reason":     result.reason,
            "source":     result.source,
        })

    async def _download_attachment(self, inp: dict) -> ToolResult:
        filename = inp.get("filename", "unknown")
        content_b64 = inp.get("content_b64", "")
        try:
            data = base64.b64decode(content_b64)
        except Exception as exc:
            return ToolResult("download_attachment", False, {}, error=f"Base64 decode failed: {exc}")

        self._attachment_cache[filename] = data
        return ToolResult("download_attachment", True, {
            "filename": filename,
            "size_bytes": len(data),
            "cached": True,
        })

    async def _save_to_excel(self, inp: dict) -> ToolResult:
        row = ReportRow(
            date=inp.get("date", ""),
            sender=inp.get("sender", ""),
            subject=inp.get("subject", ""),
            category=inp.get("category", "other"),
            confidence=float(inp.get("confidence", 0.0)),
            file_path=inp.get("file_path", ""),
            has_attachments=bool(inp.get("has_attachments", False)),
        )
        written = self._reporter.append(row)
        return ToolResult("save_to_excel", True, {
            "written": written,
            "skipped_duplicate": not written,
        })

    async def _move_file(self, inp: dict) -> ToolResult:
        filename = inp.get("filename", "unknown")
        category = inp.get("category", "other")
        sender = inp.get("sender", "")
        content_b64 = inp.get("content_b64", "")

        # Prefer cached data (from prior download_attachment call)
        data = self._attachment_cache.get(filename)
        if data is None:
            if content_b64:
                try:
                    data = base64.b64decode(content_b64)
                except Exception as exc:
                    return ToolResult("move_file", False, {}, error=f"Base64 decode failed: {exc}")
            else:
                return ToolResult("move_file", False, {}, error="No data: call download_attachment first")

        saved = self._storage.save_attachment(data, filename, category, sender=sender)
        if saved is None:
            return ToolResult("move_file", True, {"skipped": True, "reason": "duplicate"})

        return ToolResult("move_file", True, {
            "saved_path": str(saved.saved_path),
            "size_bytes": saved.size,
            "category":   saved.category,
        })
