"""
AI Agent that decides which tools to call for each email.

Flow:
  1. Agent receives email data as a task description
  2. Claude decides the tool sequence:
       classify_email → download_attachment (if any) → move_file → save_to_excel
  3. Each tool result is fed back to Claude
  4. Loop continues until Claude returns a final text answer (stop_reason = "end_turn")

Uses claude-sonnet-4-6 for agentic reasoning + tool use.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic

from backend.agent.tools.definitions import ALL_TOOLS
from backend.agent.tools.executor import ToolExecutor, ToolResult

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1024
_MAX_ITERATIONS = 10  # guard against infinite loops

_SYSTEM_PROMPT = """You are an AI email processing agent. Your job is to process emails using the tools provided.

For every email you receive, follow this sequence:
1. Call classify_email to determine the category.
2. If category is "invoice": call extract_order_data, then save_order_to_excel with the extracted data.
3. If the email has attachments: call download_attachment for each, then move_file.
4. Call save_to_excel to log the processing record.

Always complete all applicable steps. After save_to_excel, provide a concise summary."""


@dataclass
class AgentRun:
    email_uid: str
    steps: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    summary: str = ""
    success: bool = False
    error: str | None = None
    iterations: int = 0


class MailAgent:
    """Agentic loop: sends email context to Claude, executes tool calls, repeats."""

    def __init__(
        self,
        executor: ToolExecutor,
        api_key: Optional[str] = None,
        model: str = _MODEL,
    ) -> None:
        self._executor = executor
        self._client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self._model = model

    async def run(
        self,
        uid: str,
        subject: str,
        sender: str,
        body: str,
        attachments: list[dict] | None = None,
        email_date: str = "",
    ) -> AgentRun:
        run = AgentRun(email_uid=uid)

        # Build the initial user message
        attachment_info = ""
        if attachments:
            names = ", ".join(a.get("filename", "?") for a in attachments)
            attachment_info = f"\nAttachments ({len(attachments)}): {names}"

        user_message = (
            f"Process this email:\n"
            f"UID: {uid}\n"
            f"Date: {email_date or 'unknown'}\n"
            f"From: {sender}\n"
            f"Subject: {subject}\n"
            f"Body: {body[:500]}"
            f"{attachment_info}"
        )

        # Attach base64 data for each attachment in the context
        if attachments:
            for att in attachments:
                user_message += (
                    f"\n\nAttachment filename={att['filename']} "
                    f"content_b64={att.get('content_b64', '')} "
                    f"content_type={att.get('content_type', 'application/octet-stream')}"
                )

        messages: list[dict] = [{"role": "user", "content": user_message}]
        run.steps.append({"role": "user", "content": user_message})

        for iteration in range(_MAX_ITERATIONS):
            run.iterations = iteration + 1

            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                tools=ALL_TOOLS,
                messages=messages,
            )

            # Collect assistant content
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})
            run.steps.append({"role": "assistant", "content": str(assistant_content)})

            # Done — no more tool calls
            if response.stop_reason == "end_turn":
                for block in assistant_content:
                    if hasattr(block, "text"):
                        run.summary = block.text
                        break
                run.success = True
                logger.info("Agent completed uid=%s in %d iteration(s)", uid, run.iterations)
                break

            # Process tool use blocks
            if response.stop_reason == "tool_use":
                tool_results_content: list[dict] = []

                for block in assistant_content:
                    if block.type != "tool_use":
                        continue

                    logger.debug("Agent calling tool=%s uid=%s", block.name, uid)
                    result = await self._executor.execute(block.name, block.input)
                    run.tool_results.append(result)

                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.to_content(),
                    })

                messages.append({"role": "user", "content": tool_results_content})
                run.steps.append({"role": "tool_results", "content": str(tool_results_content)})
            else:
                # Unexpected stop reason
                run.error = f"Unexpected stop_reason: {response.stop_reason}"
                logger.warning("Agent unexpected stop uid=%s reason=%s", uid, response.stop_reason)
                break

        else:
            run.error = f"Agent exceeded max iterations ({_MAX_ITERATIONS})"
            logger.error("Agent loop limit reached for uid=%s", uid)

        return run
