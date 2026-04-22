from __future__ import annotations

import json
import logging
import os
from typing import Optional

import anthropic

from backend.models.email_models import ClassificationResult, EmailCategory, EmailInput
from backend.ai_service.prompts.classification_prompt import SYSTEM_PROMPT, build_classification_prompt

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {c.value for c in EmailCategory}

# claude-haiku-4-5 → fast + cheap, ideal for high-volume classification
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 150


class ClaudeClassifier:
    def __init__(self, api_key: Optional[str] = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    async def classify(self, email: EmailInput) -> ClassificationResult:
        prompt = build_classification_prompt(
            subject=email.subject,
            sender=email.sender,
            body=email.body,
        )

        response = self._client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()
        return self._parse_response(raw_text)

    def _parse_response(self, raw: str) -> ClassificationResult:
        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        data = json.loads(raw)

        category_value = data.get("category", "").lower()
        if category_value not in _VALID_CATEGORIES:
            raise ValueError(f"Invalid category from AI: {category_value!r}")

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        reason = str(data.get("reason", ""))[:300]

        return ClassificationResult(
            category=EmailCategory(category_value),
            confidence=confidence,
            reason=reason,
            source="ai",
        )
