from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

from src.models.financial import (
    BalanceProjection,
    CashflowForecast,
    CashflowItem,
    FinancialState,
    RecurringPattern,
)
from src.models.output import PlanPayment, SpendingChange


MONEY = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, _month_end(year, month))
    return date(year, month, day)


def _month_end(year: int, month: int) -> int:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - timedelta(days=1)).day


def _near_credit(known_credits: list[tuple[date, str, Decimal]], on: date, category: str, amount: Decimal) -> bool:
    for credit_on, credit_cat, credit_amt in known_credits:
        if credit_cat != category:
            continue
        if abs((credit_on - on).days) > 5:
            continue
        scale = max(abs(credit_amt), abs(amount), Decimal("1"))
        if abs(credit_amt - amount) / scale <= Decimal("0.05"):
            return True
    return False


def build_forecast(
    state: FinancialState,
    horizon_days: int = 90,
    spending_changes: Optional[list[SpendingChange]] = None,
    extra_items: Optional[list[CashflowItem]] = None,
) -> CashflowForecast:
    end_date = state.as_of + timedelta(days=horizon_days)
    changes = {item.event_id: item for item in (spending_changes or [])}
    items: list[CashflowItem] = []

    known_keys: set[tuple[date, str, str]] = set()
    known_credits: list[tuple[date, str, Decimal]] = []
    for event in state.events:
        if not event.include_in_forecast:
            continue
        if event.settlement_date < state.as_of or event.settlement_date > end_date:
            if event.status == "pending" and event.direction == "debit":
                on = max(event.settlement_date, state.as_of)
                if on <= end_date:
                    items.append(
                        CashflowItem(
                            on=on,
                            amount=event.amount_home,
                            label=event.description,
                            event_id=event.event_id,
                            category=event.category,
                            kind="pending",
                        )
                    )
                    known_keys.add((on, event.category, event.description))
            continue
        items.append(
            CashflowItem(
                on=event.settlement_date,
                amount=event.amount_home,
                label=event.description,
                event_id=event.event_id,
                category=event.category,
                kind=event.status,
            )
        )
        known_keys.add((event.settlement_date, event.category, event.description))
        if event.direction == "credit":
            known_credits.append((event.settlement_date, event.category, event.amount_home))

    for pattern in state.recurring:
        change = changes.get(pattern.event_id)
        amount = _apply_change(pattern, change)
        if amount == Decimal("0") and change and change.action == "stop":
            continue
        cursor = pattern.next_date
        while cursor <= end_date:
            key = (cursor, pattern.category, pattern.description)
            skip_income = (
                pattern.direction == "credit"
                and _near_credit(known_credits, cursor, pattern.category, amount)
            )
            if key not in known_keys and not skip_income:
                items.append(
                    CashflowItem(
                        on=cursor,
                        amount=amount,
                        label=pattern.description,
                        event_id=pattern.event_id,
                        category=pattern.category,
                        kind="recurring",
                    )
                )
                if pattern.direction == "credit":
                    known_credits.append((cursor, pattern.category, amount))
            cursor += timedelta(days=pattern.period_days)

    for category, monthly in state.residual_monthly.items():
        if monthly <= 0:
            continue
        month_cursor = add_months(date(state.as_of.year, state.as_of.month, 1), 1)
        while month_cursor <= end_date:
            items.append(
                CashflowItem(
                    on=month_cursor,
                    amount=-abs(monthly),
                    label=f"conservative {category}",
                    category=category,
                    kind="residual",
                )
            )
            month_cursor = add_months(month_cursor, 1)

    if extra_items:
        items.extend(extra_items)

    items.sort(key=lambda item: (item.on, item.amount))
    return CashflowForecast(
        start_date=state.as_of,
        end_date=end_date,
        opening_balance=state.opening_balance,
        minimum_balance=state.minimum_balance,
        currency=state.currency,
        items=items,
    )


def _apply_change(pattern: RecurringPattern, change: Optional[SpendingChange]) -> Decimal:
    if change is None:
        return pattern.amount_home
    if change.action == "stop":
        return Decimal("0")
    if change.action == "reduce_to" and change.new_amount is not None:
        signed = -abs(change.new_amount) if pattern.direction == "debit" else abs(change.new_amount)
        return signed
    return pattern.amount_home


def _day_buckets(forecast: CashflowForecast) -> tuple[list[Decimal], list[Decimal]]:
    days = (forecast.end_date - forecast.start_date).days + 1
    debits = [Decimal("0")] * days
    credits = [Decimal("0")] * days
    for item in forecast.items:
        index = (item.on - forecast.start_date).days
        if index < 0 or index >= days:
            continue
        if item.amount >= 0:
            credits[index] += item.amount
        else:
            debits[index] += item.amount
    return debits, credits


def _trough_safe(
    opening: Decimal,
    minimum: Decimal,
    debits: list[Decimal],
    credits: list[Decimal],
    payment_index: int | None = None,
    payment_amount: Decimal = Decimal("0"),
) -> tuple[bool, Decimal, Decimal, Optional[date], date]:
    balance = opening
    trough = balance
    breach_index: Optional[int] = None
    for index, debit in enumerate(debits):
        balance += debit
        if payment_index is not None and index == payment_index:
            balance -= payment_amount
        if balance < trough:
            trough = balance
        if balance < minimum and breach_index is None:
            breach_index = index
        balance += credits[index]
        if balance < trough:
            trough = balance
        if balance < minimum and breach_index is None:
            breach_index = index
    return (
        breach_index is None,
        money(trough),
        money(balance),
        breach_index,
        date.min,
    )


def project(
    forecast: CashflowForecast,
    payments: Optional[Iterable[PlanPayment]] = None,
) -> BalanceProjection:
    debits, credits = _day_buckets(forecast)
    extra: dict[int, Decimal] = {}
    if payments:
        for payment in payments:
            index = (payment.on - forecast.start_date).days
            if 0 <= index < len(debits):
                extra[index] = extra.get(index, Decimal("0")) + payment.amount
    if extra:
        debits = list(debits)
        for index, amount in extra.items():
            debits[index] -= amount
    safe, trough, ending, breach_index, _ = _trough_safe(
        forecast.opening_balance, forecast.minimum_balance, debits, credits
    )
    breach = None
    if breach_index is not None:
        breach = forecast.start_date + timedelta(days=breach_index)
    return BalanceProjection(
        safe=safe,
        trough=trough,
        ending_balance=ending,
        breach_date=breach,
    )


def is_safe(
    forecast: CashflowForecast,
    payments: Optional[Iterable[PlanPayment]] = None,
) -> bool:
    return project(forecast, payments).safe


def amount_safe_to_pay(
    forecast: CashflowForecast,
    requested: Decimal,
    request_date: date,
) -> Decimal:
    requested = money(requested)
    if requested <= 0:
        return Decimal("0")
    debits, credits = _day_buckets(forecast)
    pay_index = (request_date - forecast.start_date).days
    if pay_index < 0 or pay_index >= len(debits):
        return Decimal("0")
    opening = forecast.opening_balance
    minimum = forecast.minimum_balance
    if not _trough_safe(opening, minimum, debits, credits)[0]:
        return Decimal("0")
    if _trough_safe(opening, minimum, debits, credits, pay_index, requested)[0]:
        return requested
    low = Decimal("0")
    high = requested
    best = Decimal("0")
    for _ in range(40):
        mid = money((low + high) / 2)
        if _trough_safe(opening, minimum, debits, credits, pay_index, mid)[0]:
            best = mid
            low = mid + MONEY
        else:
            high = mid - MONEY
        if high < low:
            break
    return min(best, requested)


def earliest_full_payment_date(
    forecast: CashflowForecast,
    requested: Decimal,
    request_date: date,
) -> Optional[date]:
    requested = money(requested)
    debits, credits = _day_buckets(forecast)
    opening = forecast.opening_balance
    minimum = forecast.minimum_balance
    start_index = max(0, (request_date - forecast.start_date).days)
    for index in range(start_index, len(debits)):
        if _trough_safe(opening, minimum, debits, credits, index, requested)[0]:
            return forecast.start_date + timedelta(days=index)
    return None
