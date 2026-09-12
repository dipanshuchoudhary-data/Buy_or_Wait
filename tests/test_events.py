from datetime import date
from decimal import Decimal

from src.domain.finance.events import apply_image_amounts, apply_message_overrides, normalize_events
from src.models.domain import Direction, EventStatus, EventType, FinancialEvent, Flexibility, UserProfile
from src.models.evidence import ImageExtraction, MessageExtraction


class _HomeConverter:
    def try_convert(self, amount, from_currency, to_currency, on):
        return amount


def _event(**kwargs) -> FinancialEvent:
    data = dict(
        event_id="event_x",
        user_id="user_x",
        event_type=EventType.INCOME,
        description="Payroll credit",
        category="salary",
        direction=Direction.CREDIT,
        amount=Decimal("100"),
        currency="USD",
        event_date=date(2026, 1, 10),
        settlement_date=date(2026, 1, 10),
        status=EventStatus.PENDING,
        flexibility=Flexibility.FIXED,
    )
    data.update(kwargs)
    return FinancialEvent(**data)


def test_pending_credit_is_excluded() -> None:
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("500"),
        minimum_balance_to_keep=Decimal("100"),
    )
    normalized = normalize_events(
        [_event(status=EventStatus.PENDING, direction=Direction.CREDIT)],
        profile,
        _HomeConverter(),
        date(2026, 1, 1),
    )
    assert normalized[0].include_in_forecast is False


def test_pending_debit_is_reserved() -> None:
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("500"),
        minimum_balance_to_keep=Decimal("100"),
    )
    event = _event(
        event_type=EventType.EXPENSE,
        description="bill",
        category="utilities",
        direction=Direction.DEBIT,
        status=EventStatus.PENDING,
    )
    normalized = normalize_events([event], profile, _HomeConverter(), date(2026, 1, 1))
    assert normalized[0].include_in_forecast is True
    assert normalized[0].amount_home == Decimal("-100")


def test_unconfirmed_bonus_message_cancels_pending_credit() -> None:
    event = _event(description="Quarterly performance bonus", status=EventStatus.PENDING)
    facts = [
        MessageExtraction(
            message_id="m1",
            fact_type="unconfirmed_income",
            ignore_as_income=True,
            description="unconfirmed inbound cash",
        )
    ]
    updated = apply_message_overrides([event], facts, date(2026, 1, 1))
    assert updated[0].status == EventStatus.CANCELLED


def test_image_amount_fills_blank_event() -> None:
    event = _event(amount=None, description="Payslip")
    filled = apply_image_amounts(
        [event],
        [
            ImageExtraction(
                image_id="image_01",
                related_event_id="event_x",
                amount=Decimal("4365000"),
                currency="IDR",
            )
        ],
    )
    assert filled[0].amount == Decimal("4365000")
