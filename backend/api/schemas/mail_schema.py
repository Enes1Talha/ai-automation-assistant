from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MailSummary(BaseModel):
    id: int
    uid: str
    subject: str
    sender: str
    category: str
    confidence: float
    has_attachments: bool
    email_date: datetime
    processed_at: datetime

    model_config = {"from_attributes": True}


class MailDetail(BaseModel):
    id: int
    uid: str
    subject: str
    sender: str
    body_preview: str
    category: str
    confidence: float
    classification_reason: str
    classification_source: str
    has_attachments: bool
    attachment_count: int
    raw_size: int
    email_date: datetime
    processed_at: datetime

    model_config = {"from_attributes": True}


class CategoryStats(BaseModel):
    category: str
    count: int


class StatsResponse(BaseModel):
    total: int
    by_category: list[CategoryStats]


class ProcessResult(BaseModel):
    success: bool
    processed: int
    errors: list[str] = Field(default_factory=list)
    message: str


class MailListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MailSummary]


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
