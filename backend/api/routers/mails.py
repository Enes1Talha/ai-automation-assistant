from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database.models import MailRecord
from backend.api.schemas.mail_schema import (
    CategoryStats,
    MailDetail,
    MailListResponse,
    MailSummary,
    StatsResponse,
)

router = APIRouter(prefix="/mails", tags=["mails"])


@router.get("", response_model=MailListResponse)
def list_mails(
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> MailListResponse:
    query = db.query(MailRecord)

    if category:
        valid = {"invoice", "important", "spam", "other"}
        if category not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {valid}")
        query = query.filter(MailRecord.category == category)

    total = query.count()
    records = (
        query.order_by(MailRecord.processed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return MailListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[MailSummary.model_validate(r) for r in records],
    )


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)) -> StatsResponse:
    total = db.query(func.count(MailRecord.id)).scalar() or 0

    rows = (
        db.query(MailRecord.category, func.count(MailRecord.id))
        .group_by(MailRecord.category)
        .all()
    )

    by_category = [CategoryStats(category=cat, count=cnt) for cat, cnt in rows]
    return StatsResponse(total=total, by_category=by_category)


@router.get("/{mail_id}", response_model=MailDetail)
def get_mail(mail_id: int, db: Session = Depends(get_db)) -> MailDetail:
    record = db.query(MailRecord).filter(MailRecord.id == mail_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Mail with id={mail_id} not found")
    return MailDetail.model_validate(record)
