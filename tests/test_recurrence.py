from datetime import date
from decimal import Decimal

from src.domain.finance.recurrence import detect_recurring_patterns, is_confirmed_salary, residual_monthly_spend
from src.models.domain import Flexibility
from src.models.financial import NormalizedEvent


def _event(
    event_id: str,
    *,
    on: date,
    amount: Decimal,
    category: str = "salary",
    description: str = "Payroll credit",
    event_type: str = "income",
    direction: str = "credit",
    status: str = "settled",
    flexibility: Flexibility = Flexibility.FIXED,
    minimum=None,
) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=event_id,
        user_id="user_x",
        event_type=event_type,
        description=description,
        category=category,
        direction=direction,
        amount_home=amount,
        original_currency="USD",
        event_date=on,
        settlement_date=on,
        status=status,
        flexibility=flexibility,
        minimum_allowed_amount=minimum,
    )


def test_commission_is_not_confirmed_salary() -> None:
    event = _event("e1", on=date(2026, 1, 1), amount=Decimal("100"), description="Monthly sales commission")
    assert is_confirmed_salary(event) is False


def test_does_not_project_gig_income() -> None:
    events = [
        _event("e1", on=date(2026, 1, 7), amount=Decimal("80"), description="Weekly app earnings"),
        _event("e2", on=date(2026, 1, 14), amount=Decimal("90"), description="Weekly app earnings"),
        _event("e3", on=date(2026, 1, 21), amount=Decimal("70"), description="Weekly app earnings"),
    ]
    patterns = detect_recurring_patterns(events, date(2026, 1, 22))
    assert all(item.category != "salary" or "weekly" not in item.description.lower() for item in patterns)


def test_does_not_treat_irregular_groceries_as_weekly_series() -> None:
    events = [
        _event(
            f"g{index}",
            on=date(2026, 1, 1) + __import__("datetime").timedelta(days=7 * index),
            amount=Decimal("-40") - Decimal(index),
            category="groceries",
            description="Weekly produce market",
            event_type="expense",
            direction="debit",
        )
        for index in range(6)
    ]
    patterns = detect_recurring_patterns(events, date(2026, 2, 15))
    assert all(item.category != "groceries" for item in patterns)


def test_subscription_is_projected() -> None:
    events = [
        _event(
            "s1",
            on=date(2025, 11, 8),
            amount=Decimal("-19"),
            category="streaming",
            description="Family streaming plan",
            event_type="subscription",
            direction="debit",
            flexibility=Flexibility.STOPPABLE,
        ),
        _event(
            "s2",
            on=date(2025, 12, 8),
            amount=Decimal("-19"),
            category="streaming",
            description="Family streaming plan",
            event_type="subscription",
            direction="debit",
            flexibility=Flexibility.STOPPABLE,
        ),
    ]
    patterns = detect_recurring_patterns(events, date(2026, 1, 3))
    assert any(item.event_id == "s2" and item.period_days == 30 for item in patterns)


def test_flexible_named_dining_gets_follow_on() -> None:
    events = [
        _event(
            "d1",
            on=date(2024, 12, 18),
            amount=Decimal("-1500000"),
            category="dining",
            description="Weekend food delivery",
            event_type="expense",
            direction="debit",
            flexibility=Flexibility.REDUCIBLE,
            minimum=Decimal("665950"),
        ),
        _event(
            "d2",
            on=date(2025, 4, 23),
            amount=Decimal("-1163530.49"),
            category="dining",
            description="Weekend food delivery",
            event_type="expense",
            direction="debit",
            flexibility=Flexibility.REDUCIBLE,
            minimum=Decimal("665950"),
        ),
    ]
    patterns = detect_recurring_patterns(events, date(2025, 5, 3))
    assert any(item.event_id == "d2" and item.category == "dining" for item in patterns)


def test_residual_uses_max_recent_month() -> None:
    events = [
        _event(
            "g1",
            on=date(2026, 1, 10),
            amount=Decimal("-80"),
            category="groceries",
            description="Shop A",
            event_type="expense",
            direction="debit",
        ),
        _event(
            "g2",
            on=date(2026, 2, 10),
            amount=Decimal("-120"),
            category="groceries",
            description="Shop B",
            event_type="expense",
            direction="debit",
        ),
    ]
    residual = residual_monthly_spend(events, [], date(2026, 3, 1), [])
    assert residual["groceries"] == Decimal("120")
