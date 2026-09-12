from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from src.domain.finance.cashflow import money
from src.domain.policies.payment_policy import last_option_date, option_eligible
from src.domain.policies.user_prefs import considers
from src.models.domain import PaymentOption, Request, UserProfile
from src.models.output import CandidatePlan, PlanPayment, RecommendedMethod, SpendingChange


def _installment_payments(option: PaymentOption) -> list[PlanPayment]:
    payments = [
        PlanPayment(on=option.first_payment_date, amount=money(option.payment_amount))
    ]
    freq = option.payment_frequency_days or 0
    for index in range(1, option.number_of_payments):
        payments.append(
            PlanPayment(
                on=option.first_payment_date + timedelta(days=freq * index),
                amount=money(option.payment_amount),
            )
        )
    return payments


def generate_plans(
    request: Request,
    profile: UserProfile,
    options: list[PaymentOption],
    amount_safe: Decimal,
    earliest: date | None,
    spending_changes: list[SpendingChange] | None = None,
) -> list[CandidatePlan]:
    changes = spending_changes or []
    plans: list[CandidatePlan] = []
    deadline = request.desired_completion_date

    if considers(profile, "full_payment") and amount_safe >= request.requested_amount:
        plans.append(
            CandidatePlan(
                method=RecommendedMethod.FULL_PAYMENT,
                payments=[
                    PlanPayment(on=request.request_date, amount=money(request.requested_amount))
                ],
                spending_changes=changes,
                total_paid=money(request.requested_amount),
                completes_by_deadline=request.request_date <= deadline,
                start_date=request.request_date,
            )
        )
    elif considers(profile, "full_payment") and changes:
        plans.append(
            CandidatePlan(
                method=RecommendedMethod.FULL_PAYMENT,
                payments=[
                    PlanPayment(on=request.request_date, amount=money(request.requested_amount))
                ],
                spending_changes=changes,
                total_paid=money(request.requested_amount),
                completes_by_deadline=request.request_date <= deadline,
                start_date=request.request_date,
            )
        )

    if (
        request.allows_partial_payment
        and considers(profile, "partial_payment")
        and earliest is not None
        and earliest <= deadline
        and Decimal("0") < amount_safe < request.requested_amount
    ):
        remainder = money(request.requested_amount - amount_safe)
        plans.append(
            CandidatePlan(
                method=RecommendedMethod.PARTIAL_PAYMENT,
                payments=[
                    PlanPayment(on=request.request_date, amount=money(amount_safe)),
                    PlanPayment(on=earliest, amount=remainder),
                ],
                spending_changes=changes,
                total_paid=money(request.requested_amount),
                completes_by_deadline=True,
                start_date=request.request_date,
            )
        )

    for option in options:
        if not option_eligible(option, request, profile):
            continue
        if option.payment_method == "full_payment":
            continue
        payments = _installment_payments(option)
        last = last_option_date(option)
        plans.append(
            CandidatePlan(
                method=RecommendedMethod.INSTALLMENTS,
                payments=payments,
                spending_changes=changes,
                payment_option_id=option.payment_option_id,
                total_paid=money(option.total_payable_amount),
                completes_by_deadline=last <= deadline,
                start_date=option.first_payment_date,
            )
        )

    if (
        considers(profile, "full_payment")
        and earliest is not None
        and earliest > request.request_date
        and earliest <= deadline
    ):
        plans.append(
            CandidatePlan(
                method=RecommendedMethod.WAIT,
                payments=[PlanPayment(on=earliest, amount=money(request.requested_amount))],
                spending_changes=changes,
                total_paid=money(request.requested_amount),
                completes_by_deadline=earliest <= deadline,
                start_date=earliest,
            )
        )
    return plans
