import pytest
from backend.models.email_models import EmailCategory, EmailInput
from backend.ai_service.fallback_classifier import FallbackClassifier


@pytest.fixture
def classifier():
    return FallbackClassifier()


def _email(subject: str, sender: str = "test@example.com", body: str = "") -> EmailInput:
    return EmailInput(subject=subject, sender=sender, body=body)


class TestInvoiceClassification:
    def test_invoice_keyword_in_subject(self, classifier):
        result = classifier.classify(_email("Your invoice #1234 is ready"))
        assert result.category == EmailCategory.INVOICE
        assert result.confidence > 0.5
        assert result.source == "fallback"

    def test_receipt_in_body(self, classifier):
        result = classifier.classify(_email("Order update", body="Your receipt has been sent."))
        assert result.category == EmailCategory.INVOICE

    def test_payment_keyword(self, classifier):
        result = classifier.classify(_email("Payment confirmation"))
        assert result.category == EmailCategory.INVOICE

    def test_turkish_fatura(self, classifier):
        result = classifier.classify(_email("Faturanız hazır"))
        assert result.category == EmailCategory.INVOICE


class TestImportantClassification:
    def test_urgent_subject(self, classifier):
        result = classifier.classify(_email("URGENT: Action required on your account"))
        assert result.category == EmailCategory.IMPORTANT

    def test_password_reset(self, classifier):
        result = classifier.classify(_email("Password reset request"))
        assert result.category == EmailCategory.IMPORTANT

    def test_security_alert(self, classifier):
        result = classifier.classify(_email("Security alert", body="Unusual login detected on your account."))
        assert result.category == EmailCategory.IMPORTANT


class TestSpamClassification:
    def test_promotion_keyword(self, classifier):
        result = classifier.classify(_email("Big sale - 50% discount today only!"))
        assert result.category == EmailCategory.SPAM

    def test_unsubscribe_sender(self, classifier):
        result = classifier.classify(_email("Weekly deals", sender="noreply@shop.com", body="Click here to unsubscribe"))
        assert result.category == EmailCategory.SPAM

    def test_free_offer(self, classifier):
        result = classifier.classify(_email("You won a free gift!"))
        assert result.category == EmailCategory.SPAM


class TestOtherClassification:
    def test_no_matching_keywords(self, classifier):
        result = classifier.classify(_email("Hello there", body="How are you doing today?"))
        assert result.category == EmailCategory.OTHER
        assert result.confidence == 0.4

    def test_empty_body(self, classifier):
        result = classifier.classify(_email("", body=""))
        assert result.category == EmailCategory.OTHER


class TestPriorityOrdering:
    def test_invoice_beats_spam(self, classifier):
        # Email has both invoice and spam keywords — invoice wins
        result = classifier.classify(_email("Invoice and discount sale", body="receipt free"))
        assert result.category == EmailCategory.INVOICE

    def test_invoice_beats_important(self, classifier):
        result = classifier.classify(_email("Urgent invoice payment required"))
        assert result.category == EmailCategory.INVOICE

    def test_confidence_bounded(self, classifier):
        # Many keywords should not push confidence above 1.0
        body = " ".join(["invoice", "fatura", "receipt", "payment", "billing"] * 5)
        result = classifier.classify(_email("invoice", body=body))
        assert 0.0 <= result.confidence <= 1.0


class TestBodyTrimming:
    def test_body_trimmed_to_1000_chars(self):
        long_body = "x" * 2000
        email = EmailInput(subject="test", sender="a@b.com", body=long_body)
        assert len(email.body) == 1000
