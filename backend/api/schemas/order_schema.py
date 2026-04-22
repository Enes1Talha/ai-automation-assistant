from __future__ import annotations

from pydantic import BaseModel


class OrderItem(BaseModel):
    date: str
    sender: str
    subject: str
    order_number: str
    customer_name: str
    items_summary: str
    total_amount: float
    currency: str
    processed_at: str


class OrdersResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[OrderItem]


class CurrencyStats(BaseModel):
    currency: str
    count: int
    total: float


class OrderStatsResponse(BaseModel):
    total_orders: int
    total_revenue: float
    by_currency: list[CurrencyStats]
