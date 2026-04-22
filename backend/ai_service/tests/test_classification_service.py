import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.email_models import (
    ClassificationRequest,
    ClassificationResult,
    ClassificationResponse,
    EmailCategory,
    EmailInput,
)
from backend.ai_service.classification_service import ClassificationService


def _make_email(subject="Test", sender="a@b.com", body="Hello") -> EmailInput:
    return EmailInput(subject=subject, sender=sender, body=body)


def _make_result(category: EmailCategory, confidence: float, source: str = "ai") -> ClassificationResult:
    return ClassificationResult(
        category=category,
        confidence=confidence,
        reason="test reason",
        source=source,
    )


@pytest.fixture
def service_no_ai():
    """Service without AI (no API key set)."""
    with patch.dict("os.environ", {}, clear=True):
        svc = ClassificationService(api_key=None)
    svc._ai = None
    return svc


@pytest.fixture
def service_with_ai():
    svc = ClassificationService.__new__(ClassificationService)
    svc._threshold = 0.6
    from backend.ai_service.fallback_classifier import FallbackClassifier
    svc._fallback = FallbackClassifier()
    svc._ai = MagicMock()
    return svc


class TestFallbackOnlyMode:
    @pytest.mark.asyncio
    async def test_uses_fallback_when_no_ai(self, service_no_ai):
        req = ClassificationRequest(email=_make_email(subject="Invoice #123"))
        resp = await service_no_ai.classify(req)
        assert resp.success is True
        assert resp.result.category == EmailCategory.INVOICE
        assert resp.result.source == "fallback"

    @pytest.mark.asyncio
    async def test_other_category_fallback(self, service_no_ai):
        req = ClassificationRequest(email=_make_email(subject="Hi", body="How are you?"))
        resp = await service_no_ai.classify(req)
        assert resp.success is True
        assert resp.result.category == EmailCategory.OTHER


class TestAIWithFallback:
    @pytest.mark.asyncio
    async def test_uses_ai_when_confident(self, service_with_ai):
        service_with_ai._ai.classify = AsyncMock(
            return_value=_make_result(EmailCategory.INVOICE, 0.95)
        )
        req = ClassificationRequest(email=_make_email())
        resp = await service_with_ai.classify(req)
        assert resp.success is True
        assert resp.result.source == "ai"
        assert resp.result.category == EmailCategory.INVOICE

    @pytest.mark.asyncio
    async def test_falls_back_on_low_confidence(self, service_with_ai):
        service_with_ai._ai.classify = AsyncMock(
            return_value=_make_result(EmailCategory.INVOICE, 0.3)
        )
        req = ClassificationRequest(
            email=_make_email(subject="Payment receipt"),
            confidence_threshold=0.6,
        )
        resp = await service_with_ai.classify(req)
        assert resp.success is True
        assert resp.result.source == "fallback"

    @pytest.mark.asyncio
    async def test_falls_back_on_ai_exception(self, service_with_ai):
        service_with_ai._ai.classify = AsyncMock(side_effect=Exception("API timeout"))
        req = ClassificationRequest(email=_make_email(subject="Your receipt"))
        resp = await service_with_ai.classify(req)
        assert resp.success is True
        assert resp.result.source == "fallback"


class TestBatchClassification:
    @pytest.mark.asyncio
    async def test_batch_returns_all_results(self, service_no_ai):
        emails = [
            _make_email(subject="Invoice #1"),
            _make_email(subject="Hi there"),
            _make_email(subject="Big sale! discount!"),
        ]
        results = await service_no_ai.classify_batch(emails)
        assert len(results) == 3
        assert all(r.success for r in results)
        categories = [r.result.category for r in results]
        assert EmailCategory.INVOICE in categories
        assert EmailCategory.SPAM in categories


class TestIsReliable:
    def test_reliable_above_threshold(self):
        result = _make_result(EmailCategory.INVOICE, 0.8)
        assert result.is_reliable(0.6) is True

    def test_not_reliable_below_threshold(self):
        result = _make_result(EmailCategory.SPAM, 0.3)
        assert result.is_reliable(0.6) is False

    def test_exactly_at_threshold(self):
        result = _make_result(EmailCategory.OTHER, 0.6)
        assert result.is_reliable(0.6) is True
