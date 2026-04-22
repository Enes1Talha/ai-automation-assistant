from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.database.database import Base, get_db
from backend.database.models import MailRecord
from backend.api.main import app
from backend.api.dependencies import get_pipeline

# ── In-memory SQLite for tests — StaticPool ensures same connection ──────────
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def _seed_record(
    db: Session,
    uid: str = "1",
    subject: str = "Test",
    sender: str = "a@b.com",
    category: str = "invoice",
    confidence: float = 0.9,
    has_attachments: bool = False,
) -> MailRecord:
    record = MailRecord(
        uid=uid,
        subject=subject,
        sender=sender,
        body_preview="preview text",
        category=category,
        confidence=confidence,
        classification_reason="test reason",
        classification_source="ai",
        has_attachments=has_attachments,
        attachment_count=1 if has_attachments else 0,
        raw_size=1024,
        email_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_pipeline] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


# ── Health ────────────────────────────────────────────────────────────────────
class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── GET /mails ────────────────────────────────────────────────────────────────
class TestListMails:
    def test_empty_list(self, client):
        resp = client.get("/mails")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_returns_seeded_records(self, client, db):
        _seed_record(db, uid="1", subject="Invoice A", category="invoice")
        _seed_record(db, uid="2", subject="Meeting B", category="important")
        resp = client.get("/mails")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_filter_by_category(self, client, db):
        _seed_record(db, uid="1", category="invoice")
        _seed_record(db, uid="2", category="spam")
        _seed_record(db, uid="3", category="invoice")
        resp = client.get("/mails?category=invoice")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(i["category"] == "invoice" for i in data["items"])

    def test_filter_invalid_category_returns_400(self, client):
        resp = client.get("/mails?category=unknown")
        assert resp.status_code == 400

    def test_pagination(self, client, db):
        for i in range(5):
            _seed_record(db, uid=str(i), category="other")
        resp = client.get("/mails?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_response_contains_expected_fields(self, client, db):
        _seed_record(db, uid="1", subject="My Subject", sender="x@y.com", category="spam")
        resp = client.get("/mails")
        item = resp.json()["items"][0]
        for field in ("id", "subject", "sender", "category", "confidence", "has_attachments"):
            assert field in item


# ── GET /mails/{id} ───────────────────────────────────────────────────────────
class TestGetMailDetail:
    def test_returns_detail(self, client, db):
        record = _seed_record(db, uid="42", subject="Detail Test", category="important")
        resp = client.get(f"/mails/{record.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"] == "Detail Test"
        assert data["category"] == "important"
        for field in ("body_preview", "classification_reason", "classification_source"):
            assert field in data

    def test_returns_404_for_missing(self, client):
        resp = client.get("/mails/99999")
        assert resp.status_code == 404

    def test_detail_has_attachment_count(self, client, db):
        record = _seed_record(db, uid="5", has_attachments=True)
        resp = client.get(f"/mails/{record.id}")
        assert resp.json()["attachment_count"] == 1


# ── GET /mails/stats ──────────────────────────────────────────────────────────
class TestStats:
    def test_empty_stats(self, client):
        resp = client.get("/mails/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["by_category"] == []

    def test_stats_with_data(self, client, db):
        _seed_record(db, uid="1", category="invoice")
        _seed_record(db, uid="2", category="invoice")
        _seed_record(db, uid="3", category="spam")
        resp = client.get("/mails/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        cats = {item["category"]: item["count"] for item in data["by_category"]}
        assert cats["invoice"] == 2
        assert cats["spam"] == 1
