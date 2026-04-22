from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException

from backend.agent.agent_factory import make_mail_agent
from backend.api.schemas.agent_schema import AgentEmailRequest, AgentRunResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# Lazy singleton — only created when ANTHROPIC_API_KEY is set
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=503,
                detail="Agent unavailable: ANTHROPIC_API_KEY not configured",
            )
        _agent = make_mail_agent(
            base_dir=os.environ.get("STORAGE_BASE_DIR", "storage"),
        )
    return _agent


@router.post("/process", response_model=AgentRunResponse)
async def agent_process_email(request: AgentEmailRequest) -> AgentRunResponse:
    """
    Run the AI agent on a single email.
    The agent autonomously decides the tool sequence:
    classify → download → move → save_to_excel.
    """
    agent = _get_agent()

    attachments = [
        {
            "filename":     att.filename,
            "content_b64":  att.content_b64,
            "content_type": att.content_type,
        }
        for att in request.attachments
    ]

    run = await agent.run(
        uid=request.uid,
        subject=request.subject,
        sender=request.sender,
        body=request.body,
        attachments=attachments or None,
        email_date=request.email_date,
    )

    tools_called = [r.tool_name for r in run.tool_results]

    return AgentRunResponse(
        uid=run.email_uid,
        success=run.success,
        summary=run.summary,
        iterations=run.iterations,
        tools_called=tools_called,
        error=run.error,
    )
