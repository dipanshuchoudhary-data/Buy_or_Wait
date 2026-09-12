from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RequestType(str, Enum):
    PURCHASE = "purchase"
    TRAVEL = "travel"
    EDUCATION = "education"
    FAMILY_TRANSFER = "family_transfer"
    DEBT_REPAYMENT = "debt_repayment"
    INVESTMENT = "investment"
    HOUSING = "housing"
    EMERGENCY_EXPENSE = "emergency_expense"
    OTHER = "other"


class EventType(str, Enum):
    EXPENSE = "expense"
    DEBT_PAYMENT = "debt_payment"
    SUBSCRIPTION = "subscription"
    INCOME = "income"
    REFUND = "refund"
    INVESTMENT_PURCHASE = "investment_purchase"
    INVESTMENT_VALUATION = "investment_valuation"
    INVESTMENT_SALE = "investment_sale"


class EventStatus(str, Enum):
    SETTLED = "settled"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNREALIZED = "unrealized"


class Direction(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    NON_CASH = "non_cash"


class Flexibility(str, Enum):
    FIXED = "fixed"
    STOPPABLE = "stoppable"
    REDUCIBLE = "reducible"
    REDUCIBLE_OR_STOPPABLE = "reducible_or_stoppable"


class PaymentMethod(str, Enum):
    FULL_PAYMENT = "full_payment"
    PARTIAL_PAYMENT = "partial_payment"
    INSTALLMENTS = "installments"
    WAIT = "wait"
    NOT_RECOMMENDED = "not_recommended"


class UserProfile(BaseModel):
    user_id: str
    home_currency: str
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    financial_priorities: list[str] = Field(default_factory=list)
    expense_categories_to_protect: list[str] = Field(default_factory=list)
    expense_categories_user_is_willing_to_reduce: list[str] = Field(default_factory=list)
    expense_categories_user_is_willing_to_stop: list[str] = Field(default_factory=list)
    payment_methods_user_will_consider: list[str] = Field(default_factory=list)
    max_installment_months: Optional[int] = None


class FinancialEvent(BaseModel):
    event_id: str
    user_id: str
    event_type: EventType
    description: str
    category: str
    direction: Direction
    amount: Optional[Decimal] = None
    currency: str
    event_date: date
    settlement_date: date
    status: EventStatus
    linked_event_id: Optional[str] = None
    flexibility: Flexibility = Flexibility.FIXED
    minimum_allowed_amount: Optional[Decimal] = None


class ExchangeRate(BaseModel):
    rate_date: date
    from_currency: str
    to_currency: str
    rate: Decimal


class PaymentOption(BaseModel):
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: Decimal
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: Optional[int] = None
    financing_fee: Decimal = Decimal("0")
    total_payable_amount: Decimal


class Request(BaseModel):
    request_id: str
    user_id: str
    request_date: date
    request_type: RequestType
    requested_amount: Decimal
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str = ""


class Message(BaseModel):
    message_id: str
    user_id: str
    request_id: Optional[str] = None
    related_event_id: Optional[str] = None
    sent_at: datetime
    source_type: str
    message_text: str


class ImageRef(BaseModel):
    image_id: str
    user_id: str
    request_id: Optional[str] = None
    related_event_id: Optional[str] = None
    path: Optional[str] = None
