from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class AffordabilityStatus(str, Enum):
    AFFORDABLE_NOW = "affordable_now"
    AFFORDABLE_WITH_PLAN = "affordable_with_plan"
    AFFORDABLE_LATER = "affordable_later"
    NOT_AFFORDABLE = "not_affordable"


class RecommendedMethod(str, Enum):
    FULL_PAYMENT = "full_payment"
    PARTIAL_PAYMENT = "partial_payment"
    INSTALLMENTS = "installments"
    WAIT = "wait"
    NOT_RECOMMENDED = "not_recommended"


class PlanPayment(BaseModel):
    on: date
    amount: Decimal


class SpendingChange(BaseModel):
    action: str
    event_id: str
    new_amount: Optional[Decimal] = None

    def render(self) -> str:
        if self.action == "stop":
            return f"stop:{self.event_id}"
        if self.new_amount is None:
            raise ValueError("reduce_to requires new_amount")
        return f"reduce_to:{self.event_id}:{_format_amount(self.new_amount)}"


class CandidatePlan(BaseModel):
    method: RecommendedMethod
    payments: list[PlanPayment] = Field(default_factory=list)
    spending_changes: list[SpendingChange] = Field(default_factory=list)
    payment_option_id: Optional[str] = None
    total_paid: Decimal = Decimal("0")
    completes_by_deadline: bool = False
    start_date: Optional[date] = None
    trough: Decimal = Decimal("0")
    safe: bool = False


class DecisionOutput(BaseModel):
    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: AffordabilityStatus
    recommended_payment_method: RecommendedMethod
    payment_plan: str
    earliest_date_for_full_payment: Optional[date] = None
    spending_changes_needed: str = "none"
    decision_explanation: str

    @field_validator("decision_explanation")
    @classmethod
    def explanation_present(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("decision_explanation cannot be empty")
        return text

    @model_validator(mode="after")
    def validate_relationships(self) -> "DecisionOutput":
        if self.amount_safe_to_pay < 0:
            raise ValueError("amount_safe_to_pay cannot be negative")
        if (
            self.affordability_status == AffordabilityStatus.AFFORDABLE_NOW
            and self.earliest_date_for_full_payment is None
        ):
            raise ValueError("affordable_now requires earliest_date_for_full_payment")
        return self

    def to_row(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "amount_safe_to_pay": _format_amount(self.amount_safe_to_pay),
            "affordability_status": self.affordability_status.value,
            "recommended_payment_method": self.recommended_payment_method.value,
            "payment_plan": self.payment_plan,
            "earliest_date_for_full_payment": (
                self.earliest_date_for_full_payment.isoformat()
                if self.earliest_date_for_full_payment
                else ""
            ),
            "spending_changes_needed": self.spending_changes_needed,
            "decision_explanation": self.decision_explanation,
        }


def _format_amount(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"))
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def render_payment_plan(payments: list[PlanPayment]) -> str:
    if not payments:
        return "none"
    return "|".join(f"{item.on.isoformat()}:{_format_amount(item.amount)}" for item in payments)


def render_spending_changes(changes: list[SpendingChange]) -> str:
    if not changes:
        return "none"
    return "|".join(change.render() for change in changes[:3])
