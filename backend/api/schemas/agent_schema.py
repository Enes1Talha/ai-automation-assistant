from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class AttachmentInput(BaseModel):
    filename: str
    content_b64: str
    content_type: str = "application/octet-stream"


class AgentEmailRequest(BaseModel):
    uid: str
    subject: str
    sender: str
    body: str
    email_date: str = ""
    attachments: list[AttachmentInput] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    uid: str
    success: bool
    summary: str
    iterations: int
    tools_called: list[str]
    error: Optional[str] = None
