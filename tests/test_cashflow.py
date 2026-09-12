from datetime import date
from decimal import Decimal

from src.domain.finance.cashflow import amount_safe_to_pay, build_forecast, earliest_full_payment_date, is_safe
from src.models.financial import CashflowItem, FinancialState, NormalizedEvent
from src.models.output import PlanPayment


def test_amount_safe_caps_at_requested() -> None:
    state = FinancialState(
        user_id="user_x",
        as_of=date(2026, 1, 1),
        currency="USD",
        opening_balance=Decimal("5000"),
        minimum_balance=Decimal("100"),
        events=[],
        recurring=[],
        residual_monthly={},
    )
    forecast = build_forecast(state, horizon_days=10)
    assert amount_safe_to_pay(forecast, Decimal("250"), date(2026, 1, 1)) == Decimal("250.00")


def test_pending_debit_reduces_safe_amount() -> None:
    state = FinancialState(
        user_id="user_x",
        as_of=date(2026, 1, 1),
        currency="USD",
        opening_balance=Decimal("1000"),
        minimum_balance=Decimal("400"),
        events=[
            NormalizedEvent(
                event_id="event_x",
                user_id="user_x",
                event_type="expense",
                description="bill",
                category="utilities",
                direction="debit",
                amount_home=Decimal("-500"),
                original_currency="USD",
                event_date=date(2026, 1, 2),
                settlement_date=date(2026, 1, 2),
                status="pending",
                include_in_forecast=True,
            )
        ],
    )
    forecast = build_forecast(state, horizon_days=10)
    forecast.items.append(
        CashflowItem(on=date(2026, 1, 2), amount=Decimal("0"), label="noop")
    )
    safe = amount_safe_to_pay(forecast, Decimal("400"), date(2026, 1, 1))
    assert safe <= Decimal("100")


def test_earliest_date_moves_after_inflow() -> None:
    state = FinancialState(
        user_id="user_x",
        as_of=date(2026, 1, 1),
        currency="USD",
        opening_balance=Decimal("500"),
        minimum_balance=Decimal("400"),
        events=[
            NormalizedEvent(
                event_id="event_sal",
                user_id="user_x",
                event_type="income",
                description="salary",
                category="salary",
                direction="credit",
                amount_home=Decimal("800"),
                original_currency="USD",
                event_date=date(2026, 1, 10),
                settlement_date=date(2026, 1, 10),
                status="scheduled",
                include_in_forecast=True,
            )
        ],
    )
    forecast = build_forecast(state, horizon_days=20)
    earliest = earliest_full_payment_date(forecast, Decimal("600"), date(2026, 1, 1))
    # Income is usable after same-day essential debits, so the first safe full pay is the next day.
    assert earliest == date(2026, 1, 11)


def test_residual_is_applied_on_next_month_start() -> None:
    state = FinancialState(
        user_id="user_x",
        as_of=date(2026, 1, 3),
        currency="USD",
        opening_balance=Decimal("1000"),
        minimum_balance=Decimal("400"),
        events=[],
        residual_monthly={"groceries": Decimal("200")},
    )
    forecast = build_forecast(state, horizon_days=40)
    assert any(item.kind == "residual" and item.on == date(2026, 2, 1) for item in forecast.items)
    assert not any(item.kind == "residual" and item.on == date(2026, 1, 3) for item in forecast.items)


def test_same_day_income_cannot_fund_same_day_payment() -> None:
    state = FinancialState(
        user_id="user_x",
        as_of=date(2026, 1, 10),
        currency="USD",
        opening_balance=Decimal("400"),
        minimum_balance=Decimal("400"),
        events=[
            NormalizedEvent(
                event_id="event_sal",
                user_id="user_x",
                event_type="income",
                description="salary",
                category="salary",
                direction="credit",
                amount_home=Decimal("800"),
                original_currency="USD",
                event_date=date(2026, 1, 10),
                settlement_date=date(2026, 1, 10),
                status="scheduled",
                include_in_forecast=True,
            )
        ],
    )
    forecast = build_forecast(state, horizon_days=5)
    assert not is_safe(forecast, [PlanPayment(on=date(2026, 1, 10), amount=Decimal("500"))])
    assert is_safe(forecast, [PlanPayment(on=date(2026, 1, 11), amount=Decimal("500"))])
