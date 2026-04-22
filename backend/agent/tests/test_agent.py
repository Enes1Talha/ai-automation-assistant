import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from backend.agent.agent import MailAgent, AgentRun
from backend.agent.tools.executor import ToolExecutor, ToolResult
from backend.automation_service.excel_reporter import ExcelReporter
from backend.automation_service.storage_service import StorageService
from backend.ai_service.classification_service import ClassificationService


def _make_agent(tmp_path: Path) -> MailAgent:
    classifier = MagicMock(spec=ClassificationService)
    storage = StorageService(base_dir=tmp_path)
    reporter = ExcelReporter(report_path=tmp_path / "report.xlsx")
    executor = ToolExecutor(classifier=classifier, storage=storage, reporter=reporter)
    with patch("backend.agent.agent.anthropic.Anthropic"):
        agent = MailAgent(executor=executor, api_key="test-key")
    agent._client = MagicMock()
    return agent


def _tool_use_block(tool_name: str, tool_input: dict, block_id: str = "tu_1"):
    block = MagicMock()
    block.type = "tool_use"
    block.id = block_id
    block.name = tool_name
    block.input = tool_input
    return block


def _text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _api_response(content, stop_reason="tool_use"):
    resp = MagicMock()
    resp.content = content
    resp.stop_reason = stop_reason
    return resp


class TestAgentRun:
    @pytest.mark.asyncio
    async def test_completes_successfully_on_end_turn(self, tmp_path):
        agent = _make_agent(tmp_path)
        # First call: classify_email tool use
        # Second call: end_turn with summary
        classify_block = _tool_use_block("classify_email", {
            "subject": "Invoice", "sender": "a@b.com", "body": "pay now"
        }, "tu_1")
        excel_block = _tool_use_block("save_to_excel", {
            "date": "2024-01-01 10:00:00", "sender": "a@b.com",
            "subject": "Invoice", "category": "invoice",
            "confidence": 0.9, "file_path": "", "has_attachments": False,
        }, "tu_2")
        summary_text = _text_block("Processed email: classified as invoice, saved to Excel.")

        agent._client.messages.create.side_effect = [
            _api_response([classify_block], stop_reason="tool_use"),
            _api_response([excel_block], stop_reason="tool_use"),
            _api_response([summary_text], stop_reason="end_turn"),
        ]
        # Patch executor so tools don't need real data
        agent._executor.execute = AsyncMock(return_value=ToolResult(
            tool_name="classify_email", success=True,
            output={"category": "invoice", "confidence": 0.9, "reason": "billing", "source": "ai"}
        ))

        run = await agent.run("uid-1", "Invoice", "a@b.com", "pay now")

        assert run.success is True
        assert run.summary == "Processed email: classified as invoice, saved to Excel."
        assert run.error is None

    @pytest.mark.asyncio
    async def test_records_tool_results(self, tmp_path):
        agent = _make_agent(tmp_path)
        classify_block = _tool_use_block("classify_email", {
            "subject": "Spam", "sender": "x@x.com", "body": "free offer"
        }, "tu_1")
        summary = _text_block("Done.")

        agent._client.messages.create.side_effect = [
            _api_response([classify_block], stop_reason="tool_use"),
            _api_response([summary], stop_reason="end_turn"),
        ]
        tool_result = ToolResult("classify_email", True, {"category": "spam", "confidence": 0.85})
        agent._executor.execute = AsyncMock(return_value=tool_result)

        run = await agent.run("uid-2", "Spam", "x@x.com", "free offer")

        assert len(run.tool_results) == 1
        assert run.tool_results[0].tool_name == "classify_email"

    @pytest.mark.asyncio
    async def test_stops_after_max_iterations(self, tmp_path):
        agent = _make_agent(tmp_path)
        # Always return tool_use → never end_turn → should hit limit
        block = _tool_use_block("classify_email", {
            "subject": "x", "sender": "x", "body": "x"
        })
        agent._client.messages.create.return_value = _api_response([block], stop_reason="tool_use")
        agent._executor.execute = AsyncMock(
            return_value=ToolResult("classify_email", True, {"category": "other"})
        )

        from backend.agent.agent import _MAX_ITERATIONS
        agent._client.messages.create.side_effect = [
            _api_response([block], stop_reason="tool_use")
        ] * (_MAX_ITERATIONS + 1)

        run = await agent.run("uid-loop", "x", "x", "x")

        assert run.success is False
        assert "max iterations" in (run.error or "")

    @pytest.mark.asyncio
    async def test_uid_stored_in_run(self, tmp_path):
        agent = _make_agent(tmp_path)
        summary = _text_block("Done.")
        agent._client.messages.create.return_value = _api_response([summary], stop_reason="end_turn")

        run = await agent.run("my-special-uid", "Hi", "a@b.com", "body")
        assert run.email_uid == "my-special-uid"

    @pytest.mark.asyncio
    async def test_iterations_counted(self, tmp_path):
        agent = _make_agent(tmp_path)
        block = _tool_use_block("save_to_excel", {
            "date": "x", "sender": "x", "subject": "x",
            "category": "other", "confidence": 0.5,
            "file_path": "", "has_attachments": False,
        })
        summary = _text_block("Done.")

        agent._client.messages.create.side_effect = [
            _api_response([block], stop_reason="tool_use"),
            _api_response([summary], stop_reason="end_turn"),
        ]
        agent._executor.execute = AsyncMock(
            return_value=ToolResult("save_to_excel", True, {"written": True})
        )

        run = await agent.run("uid-3", "x", "x", "x")
        assert run.iterations == 2
