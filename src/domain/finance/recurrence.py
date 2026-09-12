from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from typing import Iterable

from src.models.domain import Flexibility
from src.models.financial import NormalizedEvent, RecurringPattern


VARIABLE_CATEGORIES = {
    "groceries",
    "transport",
    "dining",
    "shopping",
    "entertainment",
}
SERIES_CATEGORIES = {
    "rent",
    "housing",
    "utilities",
    "insurance",
    "education",
    "debt_repayment",
    "family_support",
    "healthcare",
    "gym",
    "cloud_storage",
    "streaming",
    "music_subscription",
    "delivery_membership",
    "salary",
}
SERIES_EVENT_TYPES = {"subscription", "debt_payment"}


def _group_key(event: NormalizedEvent) -> tuple[str, str, str, str]:
    return (event.event_type, event.category, event.description, event.direction)


def _period_days(intervals: list[int]) -> int | None:
    if not intervals:
        return None
    typical = median(intervals)
    if 25 <= typical <= 36:
        return 30
    if 13 <= typical <= 16:
        return 14
    if 6 <= typical <= 9:
        return 7
    if 85 <= typical <= 100:
        return 90
    return None


_UNCONFIRMED_INCOME = (
    "weekly",
    "app earnings",
    "delivery platform",
    "task marketplace",
    "driver platform",
    "final employer",
    "gig",
    "commission",
    "bonus",
    "prize",
    "lottery",
    "invoice",
    "reimbursement",
    "refund",
)


def is_confirmed_salary(event: NormalizedEvent) -> bool:
    if event.category != "salary" or event.direction != "credit":
        return False
    desc = event.description.lower()
    return not any(token in desc for token in _UNCONFIRMED_INCOME)


def _amounts_similar(items: list[NormalizedEvent]) -> bool:
    amounts = [abs(item.amount_home) for item in items]
    if not amounts:
        return False
    spread = max(amounts) - min(amounts)
    return spread <= (median(amounts) * Decimal("0.15") + Decimal("1"))


def _is_named_series(items: list[NormalizedEvent], period: int) -> bool:
    last = items[-1]
    if last.direction == "credit":
        return is_confirmed_salary(last) and period >= 28
    if last.event_type in SERIES_EVENT_TYPES:
        return True
    if last.category in SERIES_CATEGORIES:
        return True
    if last.category in VARIABLE_CATEGORIES:
        if last.flexibility != Flexibility.FIXED and _amounts_similar(items) and len(items) >= 2:
            return period >= 14
        if last.flexibility != Flexibility.FIXED and len(items) >= 2:
            desc = last.description.lower()
            if any(token in desc for token in ("delivery", "subscription", "membership", "streaming", "plan")):
                return period >= 14
        return _amounts_similar(items) and period >= 28 and len(items) >= 3
    if last.flexibility != Flexibility.FIXED:
        return period >= 28
    return period >= 28 and len(items) >= 3


def detect_recurring_patterns(
    events: list[NormalizedEvent],
    as_of: date,
) -> list[RecurringPattern]:
    historical = [
        event
        for event in events
        if event.status == "settled" and event.settlement_date <= as_of
    ]
    grouped: dict[tuple[str, str, str, str], list[NormalizedEvent]] = defaultdict(list)
    for event in historical:
        grouped[_group_key(event)].append(event)

    patterns: list[RecurringPattern] = []
    for key, items in grouped.items():
        items = sorted(items, key=lambda item: item.settlement_date)
        dates = [item.settlement_date for item in items]
        if len(dates) < 2:
            continue
        intervals = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
        period = _period_days(intervals)
        last = items[-1]
        if period is None and last.flexibility != Flexibility.FIXED and last.direction == "debit":
            desc = last.description.lower()
            named = any(
                token in desc
                for token in ("delivery", "subscription", "membership", "streaming", "plan")
            )
            if last.category not in VARIABLE_CATEGORIES or named:
                period = 30
        if period is None or not _is_named_series(items, period):
            continue
        next_date = last.settlement_date + timedelta(days=period)
        while next_date <= as_of:
            next_date += timedelta(days=period)
        patterns.append(
            RecurringPattern(
                key="|".join(key),
                event_id=last.event_id,
                event_type=last.event_type,
                description=last.description,
                category=last.category,
                direction=last.direction,
                amount_home=last.amount_home,
                period_days=period,
                next_date=next_date,
                flexibility=last.flexibility,
                minimum_allowed_amount=last.minimum_allowed_amount,
                last_settlement_date=last.settlement_date,
                confidence=1.0 if len(items) >= 3 else 0.7,
            )
        )
    patterns = _drop_salary_if_employment_ended(patterns, events, as_of)
    return _with_scheduled_salary(patterns, events, as_of)


def _drop_salary_if_employment_ended(
    patterns: list[RecurringPattern],
    events: list[NormalizedEvent],
    as_of: date,
) -> list[RecurringPattern]:
    salaries = [
        event
        for event in events
        if event.category == "salary" and event.settlement_date <= as_of
    ]
    if not salaries:
        return patterns
    latest = max(salaries, key=lambda item: item.settlement_date)
    if "final" in latest.description.lower():
        return [item for item in patterns if item.category != "salary"]
    return patterns


def _with_scheduled_salary(
    patterns: list[RecurringPattern],
    events: list[NormalizedEvent],
    as_of: date,
) -> list[RecurringPattern]:
    scheduled = [
        event
        for event in events
        if event.category == "salary"
        and event.direction == "credit"
        and event.status == "scheduled"
        and event.settlement_date >= as_of
        and is_confirmed_salary(event)
    ]
    if scheduled:
        seed = min(scheduled, key=lambda item: item.settlement_date)
        adjusted = False
        for item in patterns:
            if item.category == "salary" and item.direction == "credit":
                if abs((item.next_date - seed.settlement_date).days) <= 5:
                    item.next_date = seed.settlement_date + timedelta(days=max(item.period_days, 28))
                adjusted = True
        if adjusted:
            return patterns
        patterns.append(
            RecurringPattern(
                key=f"salary|{seed.event_id}",
                event_id=seed.event_id,
                event_type=seed.event_type,
                description=seed.description,
                category=seed.category,
                direction=seed.direction,
                amount_home=seed.amount_home,
                period_days=30,
                next_date=seed.settlement_date + timedelta(days=30),
                flexibility=seed.flexibility,
                last_settlement_date=seed.settlement_date,
                confidence=0.9,
            )
        )
        return patterns
    return patterns


def residual_monthly_spend(
    events: list[NormalizedEvent],
    patterns: list[RecurringPattern],
    as_of: date,
    protected: Iterable[str],
) -> dict[str, Decimal]:
    covered = {(item.category, item.description, item.direction) for item in patterns}
    lookback_start = as_of - timedelta(days=90)
    buckets: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    series_categories = {item.category for item in patterns if item.category in VARIABLE_CATEGORIES}
    tracked = (set(protected) | {"groceries", "transport"}) - series_categories
    for event in events:
        if event.status != "settled" or event.direction != "debit":
            continue
        if not (lookback_start <= event.settlement_date < as_of):
            continue
        if (event.category, event.description, event.direction) in covered:
            continue
        if event.category not in tracked:
            continue
        month_key = event.settlement_date.strftime("%Y-%m")
        buckets[event.category][month_key] += abs(event.amount_home)

    residual: dict[str, Decimal] = {}
    for category, months in buckets.items():
        if not months:
            continue
        values = list(months.values())
        residual[category] = max(values)
    return residual
