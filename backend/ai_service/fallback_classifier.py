from __future__ import annotations

import re
from typing import NamedTuple

from backend.models.email_models import ClassificationResult, EmailCategory, EmailInput

# Keyword sets ordered by priority: invoice > important > spam
_INVOICE_KEYWORDS = frozenset([
    "invoice", "fatura", "receipt", "makbuz", "payment", "ödeme",
    "billing", "faturalama", "order confirmation", "sipariş onayı",
    "transaction", "işlem", "charge", "ücret", "debit", "credit note",
    "purchase", "satın alma", "refund", "iade",
])

_IMPORTANT_KEYWORDS = frozenset([
    "urgent", "acil", "action required", "aksiyon gerekli",
    "important", "önemli", "deadline", "son tarih", "meeting",
    "toplantı", "contract", "sözleşme", "legal", "hukuki",
    "password reset", "şifre sıfırlama", "security alert", "güvenlik uyarısı",
    "verification", "doğrulama", "account", "hesap", "confirm",
])

_SPAM_KEYWORDS = frozenset([
    "unsubscribe", "abonelikten çık", "promotion", "promosyon",
    "sale", "indirim", "discount", "offer", "teklif", "free",
    "ücretsiz", "click here", "buraya tıkla", "newsletter", "bülten",
    "win", "kazanın", "congratulations", "tebrikler", "limited time",
    "sınırlı süre", "no-reply", "noreply", "marketing",
])


class _MatchResult(NamedTuple):
    category: EmailCategory
    hits: int
    confidence: float
    reason: str


def _count_hits(text: str, keywords: frozenset[str]) -> int:
    return sum(1 for kw in keywords if kw in text)


class FallbackClassifier:
    """Rule-based classifier used when AI is unavailable or returns low confidence."""

    def classify(self, email: EmailInput) -> ClassificationResult:
        combined = f"{email.subject} {email.sender} {email.body}".lower()

        invoice_hits = _count_hits(combined, _INVOICE_KEYWORDS)
        important_hits = _count_hits(combined, _IMPORTANT_KEYWORDS)
        spam_hits = _count_hits(combined, _SPAM_KEYWORDS)

        # Priority order: invoice > important > spam > other
        results: list[_MatchResult] = []

        if invoice_hits:
            conf = min(0.5 + invoice_hits * 0.1, 0.9)
            results.append(_MatchResult(EmailCategory.INVOICE, invoice_hits, conf, f"Matched {invoice_hits} invoice keyword(s)"))

        if important_hits:
            conf = min(0.45 + important_hits * 0.1, 0.85)
            results.append(_MatchResult(EmailCategory.IMPORTANT, important_hits, conf, f"Matched {important_hits} important keyword(s)"))

        if spam_hits:
            conf = min(0.4 + spam_hits * 0.1, 0.85)
            results.append(_MatchResult(EmailCategory.SPAM, spam_hits, conf, f"Matched {spam_hits} spam keyword(s)"))

        if not results:
            return ClassificationResult(
                category=EmailCategory.OTHER,
                confidence=0.4,
                reason="No matching keywords found",
                source="fallback",
            )

        # Pick highest priority match (list already in priority order)
        best = results[0]
        return ClassificationResult(
            category=best.category,
            confidence=best.confidence,
            reason=best.reason,
            source="fallback",
        )
