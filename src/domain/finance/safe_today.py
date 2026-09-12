from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from src.domain.finance.cashflow import amount_safe_to_pay, is_safe, money
from src.domain.finance.recurrence import is_confirmed_salary
from src.models.financial import FinancialState, NormalizedEvent, RecurringPattern
from src.models.output import SpendingChange


DEFAULT_WINDOW_DAYS = 30


def _confirmed_salary(category: str, direction: str, description: str) -> bool:
    return is_confirmed_salary(
        NormalizedEvent(
            event_id="_salary",
            user_id="_",
            event_type="income",
            description=description,
            category=category,
            direction=direction,
            amount_home=Decimal("1"),
            original_currency="USD",
            event_date=date(2000, 1, 1),
            settlement_date=date(2000, 1, 1),
            status="scheduled",
        )
    )


def next_confirmed_salary_date(state: FinancialState) -> Optional[date]:
    dates: list[date] = []
    for event in state.events:
        if event.direction != "credit" or event.category != "salary":
            continue
        if not event.include_in_forecast:
            continue
        if event.settlement_date < state.as_of:
            continue
        if event.status == "pending":
            continue
        if _confirmed_salary(event.category, event.direction, event.description):
            dates.append(event.settlement_date)
    for pattern in state.recurring:
        if pattern.direction != "credit" or pattern.category != "salary":
            continue
        if pattern.next_date < state.as_of:
            continue
        if _confirmed_salary(pattern.category, pattern.direction, pattern.description):
            dates.append(pattern.next_date)
    return min(dates) if dates else None


def _window_end(state: FinancialState) -> date:
    nxt = next_confirmed_salary_date(state)
    if nxt is None:
        return state.as_of + timedelta(days=DEFAULT_WINDOW_DAYS)
    return nxt


def _apply_change(pattern: RecurringPattern, change: Optional[SpendingChange]) -> Decimal:
    if change is None:
        return pattern.amount_home
    if change.action == "stop":
        return Decimal("0")
    if change.action == "reduce_to" and change.new_amount is not None:
        signed = -abs(change.new_amount) if pattern.direction == "debit" else abs(change.new_amount)
        return signed
    return pattern.amount_home


def near_term_cash_cap(
    state: FinancialState,
    spending_changes: Optional[list[SpendingChange]] = None,
) -> Decimal:
    headroom = state.opening_balance - state.minimum_balance
    if headroom <= 0:
        return Decimal("0")

    window_end = _window_end(state)
    changes = {item.event_id: item for item in (spending_changes or [])}
    reserved = Decimal("0")
    seen: set[tuple[date, str, str]] = set()

    for event in state.events:
        if event.direction != "debit":
            continue
        if not event.include_in_forecast and event.status != "pending":
            continue
        on = event.settlement_date
        if event.status == "pending":
            on = max(event.settlement_date, state.as_of)
        if on < state.as_of or on > window_end:
            continue
        reserved += abs(event.amount_home)
        seen.add((on, event.category, event.description))

    for pattern in state.recurring:
        if pattern.direction != "debit":
            continue
        amount = _apply_change(pattern, changes.get(pattern.event_id))
        if amount == 0:
            continue
        cursor = pattern.next_date
        while cursor <= window_end:
            key = (cursor, pattern.category, pattern.description)
            if cursor >= state.as_of and key not in seen:
                reserved += abs(amount)
                seen.add(key)
            cursor += timedelta(days=pattern.period_days)

    window_days = max(0, (window_end - state.as_of).days)
    for category, monthly in state.residual_monthly.items():
        if monthly <= 0:
            continue
        reserved += abs(monthly) / Decimal("30") * Decimal(window_days)

    return money(max(Decimal("0"), headroom - reserved))


def amount_safe_to_pay_today(
    state: FinancialState,
    forecast,
    requested: Decimal,
    request_date: date,
    spending_changes: Optional[list[SpendingChange]] = None,
) -> Decimal:
    requested = money(requested)
    if requested <= 0:
        return Decimal("0")
    if not is_safe(forecast):
        return Decimal("0")
    simulated = amount_safe_to_pay(forecast, requested, request_date)
    cap = near_term_cash_cap(state, spending_changes)
    return min(requested, simulated, cap)
