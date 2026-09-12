from datetime import date
from decimal import Decimal

from src.domain.policies.spending_policy import change_combinations, eligible_changes
from src.models.domain import Flexibility, UserProfile
from src.models.financial import RecurringPattern


def _pattern(event_id: str, category: str, flexibility: Flexibility) -> RecurringPattern:
    return RecurringPattern(
        key=event_id,
        event_id=event_id,
        event_type="subscription",
        description=event_id,
        category=category,
        direction="debit",
        amount_home=Decimal("-20"),
        period_days=30,
        next_date=date(2026, 1, 10),
        flexibility=flexibility,
        minimum_allowed_amount=Decimal("10"),
        last_settlement_date=date(2025, 12, 10),
    )


def test_protected_category_cannot_be_changed() -> None:
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("100"),
        minimum_balance_to_keep=Decimal("10"),
        expense_categories_to_protect=["rent"],
        expense_categories_user_is_willing_to_stop=["rent"],
    )
    changes = eligible_changes(profile, [_pattern("event_rent", "rent", Flexibility.STOPPABLE)])
    assert changes == []


def test_stoppable_permitted_category_is_eligible() -> None:
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("100"),
        minimum_balance_to_keep=Decimal("10"),
        expense_categories_user_is_willing_to_stop=["streaming"],
    )
    changes = eligible_changes(profile, [_pattern("event_stream", "streaming", Flexibility.STOPPABLE)])
    assert changes[0].action == "stop"
    assert changes[0].event_id == "event_stream"


def test_combinations_do_not_repeat_the_same_event() -> None:
    profile = UserProfile(
        user_id="user_x",
        home_currency="USD",
        current_available_balance=Decimal("100"),
        minimum_balance_to_keep=Decimal("10"),
        expense_categories_user_is_willing_to_stop=["streaming"],
        expense_categories_user_is_willing_to_reduce=["streaming"],
    )
    candidates = eligible_changes(
        profile, [_pattern("event_stream", "streaming", Flexibility.REDUCIBLE_OR_STOPPABLE)]
    )
    combos = change_combinations(candidates, max_changes=2)
    for combo in combos:
        ids = [item.event_id for item in combo]
        assert len(ids) == len(set(ids))
