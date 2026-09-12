from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.finance.cashflow import money
from src.models.domain import Request, UserProfile
from src.models.output import (
    AffordabilityStatus,
    CandidatePlan,
    DecisionOutput,
    RecommendedMethod,
    render_payment_plan,
    render_spending_changes,
)


def build_decision(
    request: Request,
    profile: UserProfile,
    amount_safe: Decimal,
    earliest: Optional[date],
    selected: Optional[CandidatePlan],
    explanation: str,
) -> DecisionOutput:
    amount_safe = money(min(max(amount_safe, Decimal("0")), request.requested_amount))
    if selected is None:
        status = (
            AffordabilityStatus.AFFORDABLE_LATER
            if earliest is not None
            else AffordabilityStatus.NOT_AFFORDABLE
        )
        method = RecommendedMethod.NOT_RECOMMENDED
        plan_text = "none"
        changes = "none"
    else:
        method = selected.method
        plan_text = render_payment_plan(selected.payments)
        changes = render_spending_changes(selected.spending_changes)
        if method == RecommendedMethod.FULL_PAYMENT and not selected.spending_changes:
            status = AffordabilityStatus.AFFORDABLE_NOW
        elif method == RecommendedMethod.WAIT:
            status = AffordabilityStatus.AFFORDABLE_LATER
        elif method == RecommendedMethod.NOT_RECOMMENDED:
            status = AffordabilityStatus.NOT_AFFORDABLE
        else:
            status = AffordabilityStatus.AFFORDABLE_WITH_PLAN
        if selected.spending_changes and method == RecommendedMethod.FULL_PAYMENT:
            status = AffordabilityStatus.AFFORDABLE_WITH_PLAN

    if status == AffordabilityStatus.AFFORDABLE_NOW:
        earliest = request.request_date

    return DecisionOutput(
        request_id=request.request_id,
        amount_safe_to_pay=amount_safe,
        affordability_status=status,
        recommended_payment_method=method,
        payment_plan=plan_text,
        earliest_date_for_full_payment=earliest,
        spending_changes_needed=changes,
        decision_explanation=explanation,
    )
