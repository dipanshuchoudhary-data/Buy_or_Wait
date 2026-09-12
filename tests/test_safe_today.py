from datetime import date
from decimal import Decimal

from src.domain.finance.cashflow import amount_safe_to_pay, build_forecast
from src.domain.finance.safe_today import (
    amount_safe_to_pay_today,
    near_term_cash_cap,
    next_confirmed_salary_date,
)
from src.models.financial import FinancialState, NormalizedEvent, RecurringPattern


def _state(**kwargs) -> FinancialState:
    data = dict(
        user_id="user_x",
        as_of=date(2026, 1, 1),
        currency="USD",
        opening_balance=Decimal("2000"),
        minimum_balance=Decimal("400"),
        events=[],
        recurring=[],
        residual_monthly={},
    )
    data.update(kwargs)
    return FinancialState(**data)


def _debit_event(event_id: str, on: date, amount: Decimal, status: str = "pending") -> NormalizedEvent:
    return NormalizedEvent(
        event_id=event_id,
        user_id="user_x",
        event_type="expense",
        description=event_id,
        category="utilities",
        direction="debit",
        amount_home=-abs(amount),
        original_currency="USD",
        event_date=on,
        settlement_date=on,
        status=status,
        include_in_forecast=True,
    )


def _salary_event(on: date, amount: Decimal = Decimal("800")) -> NormalizedEvent:
    return NormalizedEvent(
        event_id="event_sal",
        user_id="user_x",
        event_type="income",
        description="Payroll credit",
        category="salary",
        direction="credit",
        amount_home=amount,
        original_currency="USD",
        event_date=on,
        settlement_date=on,
        status="scheduled",
        include_in_forecast=True,
    )


def _rent_pattern(on: date, amount: Decimal = Decimal("-500")) -> RecurringPattern:
    return RecurringPattern(
        key="rent",
        event_id="event_rent",
        event_type="expense",
        description="Monthly rent",
        category="rent",
        direction="debit",
        amount_home=amount,
        period_days=30,
        next_date=on,
        last_settlement_date=date(2025, 12, 1),
    )


def test_cap_ignores_salary_credit_inside_the_window() -> None:
    state = _state(events=[_salary_event(date(2026, 1, 10), Decimal("5000"))])
    cap = near_term_cash_cap(state)
    assert cap == Decimal("1600.00")
    assert next_confirmed_salary_date(state) == date(2026, 1, 10)


def test_pending_debit_and_rent_reduce_the_cap() -> None:
    state = _state(
        events=[_debit_event("bill", date(2026, 1, 5), Decimal("200"))],
        recurring=[_rent_pattern(date(2026, 1, 8))],
    )
    cap = near_term_cash_cap(state)
    assert cap == Decimal("900.00")


def test_grocery_residual_scales_with_window_length() -> None:
    short = _state(
        events=[_salary_event(date(2026, 1, 11))],
        residual_monthly={"groceries": Decimal("300")},
    )
    long = _state(
        events=[_salary_event(date(2026, 1, 21))],
        residual_monthly={"groceries": Decimal("300")},
    )
    short_cap = near_term_cash_cap(short)
    long_cap = near_term_cash_cap(long)
    assert short_cap > long_cap
    assert short_cap - long_cap == Decimal("100.00")


def test_forecast_has_no_current_month_residual_on_as_of() -> None:
    state = _state(residual_monthly={"groceries": Decimal("200")})
    forecast = build_forecast(state, horizon_days=40)
    assert not any(item.kind == "residual" and item.on == date(2026, 1, 1) for item in forecast.items)
    assert any(item.kind == "residual" and item.on == date(2026, 2, 1) for item in forecast.items)


def test_today_amount_is_min_of_requested_sim_and_cap() -> None:
    state = _state(
        opening_balance=Decimal("5000"),
        minimum_balance=Decimal("100"),
        events=[_debit_event("bill", date(2026, 1, 2), Decimal("200"))],
    )
    forecast = build_forecast(state, horizon_days=10)
    simulated = amount_safe_to_pay(forecast, Decimal("250"), date(2026, 1, 1))
    cap = near_term_cash_cap(state)
    today = amount_safe_to_pay_today(state, forecast, Decimal("250"), date(2026, 1, 1))
    assert simulated == Decimal("250.00")
    assert cap == Decimal("4700.00")
    assert today == Decimal("250.00")

    tight = amount_safe_to_pay_today(state, forecast, Decimal("8000"), date(2026, 1, 1))
    assert tight == cap


def test_already_breaching_forecast_returns_zero() -> None:
    state = _state(
        opening_balance=Decimal("100"),
        minimum_balance=Decimal("400"),
        events=[_debit_event("bill", date(2026, 1, 2), Decimal("50"), status="scheduled")],
    )
    forecast = build_forecast(state, horizon_days=10)
    assert amount_safe_to_pay_today(state, forecast, Decimal("80"), date(2026, 1, 1)) == Decimal("0")
