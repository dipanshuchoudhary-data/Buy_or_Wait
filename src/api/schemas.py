from __future__ import annotations

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    request_id: str


class AnalyzeResponse(BaseModel):
    request_id: str
    amount_safe_to_pay: str
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str
