from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Query

from backend.automation_service.order_reader import OrderReader
from backend.api.schemas.order_schema import (
    CurrencyStats,
    OrderItem,
    OrderStatsResponse,
    OrdersResponse,
)

router = APIRouter(prefix="/orders", tags=["orders"])

_reader: OrderReader | None = None


def _get_reader() -> OrderReader:
    global _reader
    if _reader is None:
        base = os.environ.get("STORAGE_BASE_DIR", "storage")
        _reader = OrderReader(report_path=Path(base) / "report.xlsx")
    return _reader


@router.get("", response_model=OrdersResponse)
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> OrdersResponse:
    reader = _get_reader()
    total, rows = reader.list_orders(page=page, page_size=page_size)
    return OrdersResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            OrderItem(
                date=r.date,
                sender=r.sender,
                subject=r.subject,
                order_number=r.order_number,
                customer_name=r.customer_name,
                items_summary=r.items_summary,
                total_amount=r.total_amount,
                currency=r.currency,
                processed_at=r.processed_at,
            )
            for r in rows
        ],
    )


@router.get("/stats", response_model=OrderStatsResponse)
def get_order_stats() -> OrderStatsResponse:
    reader = _get_reader()
    stats = reader.get_stats()
    return OrderStatsResponse(
        total_orders=stats.total_orders,
        total_revenue=stats.total_revenue,
        by_currency=[
            CurrencyStats(currency=s.currency, count=s.count, total=s.total)
            for s in stats.by_currency
        ],
    )
