from __future__ import annotations

import logging
import os
from typing import Optional

from backend.models.email_models import (
    ClassificationResult,
    ClassificationRequest,
    ClassificationResponse,
    EmailInput,
)
from backend.ai_service.claude_classifier import ClaudeClassifier
from backend.ai_service.fallback_classifier import FallbackClassifier

logger = logging.getLogger(__name__)


class ClassificationService:
    """
    Orchestrates AI + fallback classification.

    Flow:
      1. Try Claude AI classifier
      2. If AI fails OR confidence < threshold → use fallback
      3. If fallback also fails → return safe default (OTHER, 0.0)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        confidence_threshold: float = 0.6,
    ):
        self._threshold = confidence_threshold
        self._fallback = FallbackClassifier()
        self._ai: Optional[ClaudeClassifier] = None

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if resolved_key:
            self._ai = ClaudeClassifier(api_key=resolved_key)
        else:
            logger.warning("ANTHROPIC_API_KEY not set — running in fallback-only mode")

    async def classify(self, request: ClassificationRequest) -> ClassificationResponse:
        email = request.email
        threshold = request.confidence_threshold or self._threshold

        # Attempt AI classification
        if self._ai is not None:
            try:
                result = await self._ai.classify(email)
                if result.is_reliable(threshold):
                    logger.info(
                        "AI classified email from=%s category=%s confidence=%.2f",
                        email.sender,
                        result.category,
                        result.confidence,
                    )
                    return ClassificationResponse(success=True, result=result)

                logger.info(
                    "AI confidence %.2f below threshold %.2f — using fallback",
                    result.confidence,
                    threshold,
                )
            except Exception as exc:
                logger.warning("AI classification failed: %s — using fallback", exc)

        # Fallback classification
        try:
            result = self._fallback.classify(email)
            logger.info(
                "Fallback classified email from=%s category=%s",
                email.sender,
                result.category,
            )
            return ClassificationResponse(success=True, result=result)
        except Exception as exc:
            logger.error("Fallback classification failed: %s", exc)
            return ClassificationResponse(
                success=False,
                error=f"Classification failed: {exc}",
            )

    async def classify_batch(
        self, emails: list[EmailInput], confidence_threshold: float = 0.6
    ) -> list[ClassificationResponse]:
        import asyncio

        tasks = [
            self.classify(ClassificationRequest(email=e, confidence_threshold=confidence_threshold))
            for e in emails
        ]
        return list(await asyncio.gather(*tasks))
