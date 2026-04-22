"""
Extracts structured order data from invoice/order emails using Claude haiku.
Returns an OrderData dataclass; on failure returns a zero-filled instance.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 256

_SYSTEM = (
    "You extract order data from email text. "
    "Respond ONLY with a valid JSON object — no markdown, no explanation. "
    "If a field is not found, use an empty string or 0."
)

_PROMPT_TEMPLATE = """\
Extract order information from this email:

Subject: {subject}
From: {sender}
Body:
{body}

Return JSON with exactly these keys:
{{
  "order_number": "<string>",
  "customer_name": "<string>",
  "items_summary": "<comma-separated list of item x qty>",
  "total_amount": <number>,
  "currency": "<3-letter ISO code, e.g. USD>"
}}"""


@dataclass
class OrderData:
    order_number: str = ""
    customer_name: str = ""
    items_summary: str = ""
    total_amount: float = 0.0
    currency: str = ""
    extracted: bool = True


class OrderExtractorService:
    """Calls Claude haiku to extract order fields from an email."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", ""))

    async def extract(self, subject: str, sender: str, body: str) -> OrderData:
        prompt = _PROMPT_TEMPLATE.format(
            subject=subject,
            sender=sender,
            body=body[:800],
        )
        try:
            response = self._client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown fences if present
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            data = json.loads(raw)
            return OrderData(
                order_number=str(data.get("order_number", "")),
                customer_name=str(data.get("customer_name", "")),
                items_summary=str(data.get("items_summary", "")),
                total_amount=float(data.get("total_amount", 0.0)),
                currency=str(data.get("currency", "")),
                extracted=True,
            )
        except Exception as exc:
            logger.warning("Order extraction failed: %s", exc)
            return OrderData(extracted=False)
