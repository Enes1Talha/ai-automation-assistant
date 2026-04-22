import json
import pytest
from unittest.mock import MagicMock, patch

from backend.models.email_models import EmailCategory, EmailInput
from backend.ai_service.claude_classifier import ClaudeClassifier


def _make_email(subject="Test invoice", sender="vendor@co.com", body="Please pay invoice #42") -> EmailInput:
    return EmailInput(subject=subject, sender=sender, body=body)


def _mock_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


@pytest.fixture
def classifier():
    with patch("backend.ai_service.claude_classifier.anthropic.Anthropic"):
        clf = ClaudeClassifier(api_key="test-key")
    clf._client = MagicMock()
    return clf


class TestParseResponse:
    def test_valid_invoice_response(self, classifier):
        raw = json.dumps({"category": "invoice", "confidence": 0.92, "reason": "Contains billing info"})
        result = classifier._parse_response(raw)
        assert result.category == EmailCategory.INVOICE
        assert result.confidence == 0.92
        assert result.source == "ai"

    def test_valid_spam_response(self, classifier):
        raw = json.dumps({"category": "spam", "confidence": 0.88, "reason": "Promotional content"})
        result = classifier._parse_response(raw)
        assert result.category == EmailCategory.SPAM

    def test_strips_markdown_code_fences(self, classifier):
        raw = "```json\n{\"category\": \"important\", \"confidence\": 0.75, \"reason\": \"Urgent action\"}\n```"
        result = classifier._parse_response(raw)
        assert result.category == EmailCategory.IMPORTANT

    def test_confidence_clamped_above_1(self, classifier):
        raw = json.dumps({"category": "other", "confidence": 1.5, "reason": "x"})
        result = classifier._parse_response(raw)
        assert result.confidence == 1.0

    def test_confidence_clamped_below_0(self, classifier):
        raw = json.dumps({"category": "other", "confidence": -0.3, "reason": "x"})
        result = classifier._parse_response(raw)
        assert result.confidence == 0.0

    def test_invalid_category_raises(self, classifier):
        raw = json.dumps({"category": "unknown", "confidence": 0.9, "reason": "x"})
        with pytest.raises(ValueError, match="Invalid category"):
            classifier._parse_response(raw)

    def test_invalid_json_raises(self, classifier):
        with pytest.raises(json.JSONDecodeError):
            classifier._parse_response("not json at all")

    def test_reason_truncated_to_300(self, classifier):
        long_reason = "x" * 500
        raw = json.dumps({"category": "other", "confidence": 0.5, "reason": long_reason})
        result = classifier._parse_response(raw)
        assert len(result.reason) == 300


class TestClassifyIntegration:
    @pytest.mark.asyncio
    async def test_classify_calls_api(self, classifier):
        classifier._client.messages.create.return_value = _mock_response(
            json.dumps({"category": "invoice", "confidence": 0.9, "reason": "Has payment info"})
        )
        result = await classifier.classify(_make_email())
        assert result.category == EmailCategory.INVOICE
        classifier._client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_uses_correct_model(self, classifier):
        classifier._client.messages.create.return_value = _mock_response(
            json.dumps({"category": "spam", "confidence": 0.8, "reason": "Promo"})
        )
        await classifier.classify(_make_email())
        call_kwargs = classifier._client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["max_tokens"] == 150
