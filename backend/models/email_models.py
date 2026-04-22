from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class EmailCategory(str, Enum):
    INVOICE = "invoice"
    IMPORTANT = "important"
    SPAM = "spam"
    OTHER = "other"


class EmailInput(BaseModel):
    subject: str = Field(..., min_length=0, max_length=500, description="Email subject line")
    sender: str = Field(..., description="Sender email address or display name")
    body: str = Field(..., description="Email body text (trimmed to 1000 chars internally)")

    @field_validator("body")
    @classmethod
    def trim_body(cls, v: str) -> str:
        return v[:1000]

    @field_validator("sender")
    @classmethod
    def normalize_sender(cls, v: str) -> str:
        return v.strip().lower()


class ClassificationResult(BaseModel):
    category: EmailCategory
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reason: str = Field(..., max_length=300, description="Short explanation for the classification")
    source: str = Field(default="ai", description="'ai' or 'fallback'")

    def is_reliable(self, threshold: float = 0.6) -> bool:
        return self.confidence >= threshold


class ClassificationRequest(BaseModel):
    email: EmailInput
    confidence_threshold: Optional[float] = Field(default=0.6, ge=0.0, le=1.0)


class ClassificationResponse(BaseModel):
    success: bool
    result: Optional[ClassificationResult] = None
    error: Optional[str] = None
