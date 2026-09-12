from datetime import date
from decimal import Decimal

from src.domain.payments.planner import generate_plans
from src.models.domain import PaymentOption, Request, RequestType, UserProfile


def test_partial_plan_has_two_legs() -> None:
    request = Request(
        request_id="request_x",
        user_id="user_x",
        request_date=date(2026, 1, 1),
        request_type=RequestType.PURCHASE,
        requested_amount=Decimal("100"),
        desired_completion_date=date(2026, 2, 1),
        allows_partial_payment=True,
    )
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("80"),
        minimum_balance_to_keep=Decimal("10"),
        payment_methods_user_will_consider=["partial_payment"],
    )
    plans = generate_plans(
        request,
        profile,
        [],
        Decimal("40"),
        date(2026, 1, 20),
        [],
    )
    partial = next(plan for plan in plans if plan.method.value == "partial_payment")
    assert len(partial.payments) == 2
    assert sum((item.amount for item in partial.payments), start=Decimal("0")) == Decimal("100")


def test_installment_uses_supplied_option() -> None:
    request = Request(
        request_id="request_x",
        user_id="user_x",
        request_date=date(2026, 1, 1),
        request_type=RequestType.PURCHASE,
        requested_amount=Decimal("90"),
        desired_completion_date=date(2026, 4, 1),
        allows_partial_payment=False,
    )
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("80"),
        minimum_balance_to_keep=Decimal("10"),
        payment_methods_user_will_consider=["installments"],
        max_installment_months=6,
    )
    option = PaymentOption(
        payment_option_id="payment_option_99",
        request_id="request_x",
        payment_method="installments",
        payment_amount=Decimal("30"),
        number_of_payments=3,
        first_payment_date=date(2026, 1, 10),
        payment_frequency_days=30,
        financing_fee=Decimal("0"),
        total_payable_amount=Decimal("90"),
    )
    plans = generate_plans(request, profile, [option], Decimal("20"), None, [])
    inst = next(plan for plan in plans if plan.method.value == "installments")
    assert [item.amount for item in inst.payments] == [Decimal("30.00")] * 3
    assert inst.payment_option_id == "payment_option_99"


def test_wait_after_deadline_is_not_generated() -> None:
    request = Request(
        request_id="request_x",
        user_id="user_x",
        request_date=date(2026, 1, 1),
        request_type=RequestType.PURCHASE,
        requested_amount=Decimal("100"),
        desired_completion_date=date(2026, 1, 10),
        allows_partial_payment=False,
    )
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("20"),
        minimum_balance_to_keep=Decimal("10"),
        payment_methods_user_will_consider=["full_payment"],
    )
    plans = generate_plans(request, profile, [], Decimal("10"), date(2026, 2, 1), [])
    assert all(plan.method.value != "wait" for plan in plans)
