from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from src.models.domain import Flexibility


class NormalizedEvent(BaseModel):
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount_home: Decimal
    original_amount: Optional[Decimal] = None
    original_currency: str
    event_date: date
    settlement_date: date
    status: str
    linked_event_id: Optional[str] = None
    flexibility: Flexibility = Flexibility.FIXED
    minimum_allowed_amount: Optional[Decimal] = None
    source: str = "event"
    include_in_forecast: bool = False
    already_in_balance: bool = False


class RecurringPattern(BaseModel):
    key: str
    event_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount_home: Decimal
    period_days: int
    next_date: date
    flexibility: Flexibility = Flexibility.FIXED
    minimum_allowed_amount: Optional[Decimal] = None
    last_settlement_date: date
    confidence: float = 1.0


class CashflowItem(BaseModel):
    on: date
    amount: Decimal
    label: str
    event_id: Optional[str] = None
    category: Optional[str] = None
    kind: str = "forecast"


class CashflowForecast(BaseModel):
    start_date: date
    end_date: date
    opening_balance: Decimal
    minimum_balance: Decimal
    currency: str
    items: list[CashflowItem] = Field(default_factory=list)


class BalanceProjection(BaseModel):
    safe: bool
    trough: Decimal
    ending_balance: Decimal
    breach_date: Optional[date] = None


class FinancialState(BaseModel):
    user_id: str
    as_of: date
    currency: str
    opening_balance: Decimal
    minimum_balance: Decimal
    events: list[NormalizedEvent] = Field(default_factory=list)
    recurring: list[RecurringPattern] = Field(default_factory=list)
    residual_monthly: dict[str, Decimal] = Field(default_factory=dict)
