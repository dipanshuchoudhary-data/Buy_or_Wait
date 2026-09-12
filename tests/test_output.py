from datetime import date
from decimal import Decimal

from src.domain.decisions.builder import build_decision
from src.models.domain import Request, RequestType, UserProfile
from src.models.output import (
    AffordabilityStatus,
    CandidatePlan,
    DecisionOutput,
    PlanPayment,
    RecommendedMethod,
    SpendingChange,
)


def test_output_row_order_and_bounds() -> None:
    decision = DecisionOutput(
        request_id="request_01",
        amount_safe_to_pay=Decimal("10"),
        affordability_status=AffordabilityStatus.AFFORDABLE_NOW,
        recommended_payment_method=RecommendedMethod.FULL_PAYMENT,
        payment_plan="2024-03-03:10",
        earliest_date_for_full_payment=date(2024, 3, 3),
        spending_changes_needed="none",
        decision_explanation="Pay 10 today.",
    )
    row = decision.to_row()
    assert list(row.keys()) == [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ]
    assert Decimal(row["amount_safe_to_pay"]) <= Decimal("10")


def test_affordable_now_forces_request_date() -> None:
    request = Request(
        request_id="request_x",
        user_id="user_x",
        request_date=date(2026, 1, 1),
        request_type=RequestType.PURCHASE,
        requested_amount=Decimal("50"),
        desired_completion_date=date(2026, 1, 20),
        allows_partial_payment=False,
    )
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("100"),
        minimum_balance_to_keep=Decimal("10"),
    )
    selected = CandidatePlan(
        method=RecommendedMethod.FULL_PAYMENT,
        payments=[PlanPayment(on=date(2026, 1, 1), amount=Decimal("50"))],
        total_paid=Decimal("50"),
        completes_by_deadline=True,
        start_date=date(2026, 1, 1),
    )
    decision = build_decision(request, profile, Decimal("50"), None, selected, "Pay today.")
    assert decision.affordability_status == AffordabilityStatus.AFFORDABLE_NOW
    assert decision.earliest_date_for_full_payment == date(2026, 1, 1)


def test_spending_change_full_payment_is_with_plan() -> None:
    request = Request(
        request_id="request_x",
        user_id="user_x",
        request_date=date(2026, 1, 1),
        request_type=RequestType.PURCHASE,
        requested_amount=Decimal("50"),
        desired_completion_date=date(2026, 1, 20),
        allows_partial_payment=False,
    )
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("100"),
        minimum_balance_to_keep=Decimal("10"),
    )
    selected = CandidatePlan(
        method=RecommendedMethod.FULL_PAYMENT,
        payments=[PlanPayment(on=date(2026, 1, 1), amount=Decimal("50"))],
        spending_changes=[SpendingChange(action="stop", event_id="event_1")],
        total_paid=Decimal("50"),
        completes_by_deadline=True,
        start_date=date(2026, 1, 1),
    )
    decision = build_decision(request, profile, Decimal("40"), date(2026, 1, 15), selected, "Stop then pay.")
    assert decision.affordability_status == AffordabilityStatus.AFFORDABLE_WITH_PLAN
    assert decision.spending_changes_needed == "stop:event_1"
