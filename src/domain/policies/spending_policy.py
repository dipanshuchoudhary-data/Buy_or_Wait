from __future__ import annotations

from src.models.domain import Flexibility, UserProfile
from src.models.financial import RecurringPattern
from src.models.output import SpendingChange


def eligible_changes(
    profile: UserProfile, patterns: list[RecurringPattern]
) -> list[SpendingChange]:
    protected = set(profile.expense_categories_to_protect)
    reduce_ok = set(profile.expense_categories_user_is_willing_to_reduce)
    stop_ok = set(profile.expense_categories_user_is_willing_to_stop)
    candidates: list[SpendingChange] = []
    for pattern in patterns:
        if pattern.direction != "debit":
            continue
        if pattern.category in protected:
            continue
        if pattern.flexibility == Flexibility.FIXED:
            continue
        can_stop = pattern.flexibility in {
            Flexibility.STOPPABLE,
            Flexibility.REDUCIBLE_OR_STOPPABLE,
        } and pattern.category in stop_ok
        can_reduce = pattern.flexibility in {
            Flexibility.REDUCIBLE,
            Flexibility.REDUCIBLE_OR_STOPPABLE,
        } and pattern.category in reduce_ok
        if can_stop:
            candidates.append(SpendingChange(action="stop", event_id=pattern.event_id))
        if can_reduce and pattern.minimum_allowed_amount is not None:
            candidates.append(
                SpendingChange(
                    action="reduce_to",
                    event_id=pattern.event_id,
                    new_amount=pattern.minimum_allowed_amount,
                )
            )
    return candidates


def change_combinations(candidates: list[SpendingChange], max_changes: int = 3) -> list[list[SpendingChange]]:
    ranked = sorted(candidates, key=lambda item: (item.action != "stop", item.event_id))[:8]
    results: list[list[SpendingChange]] = [[]]
    used_pairs: set[tuple[str, ...]] = set()

    def add(combo: list[SpendingChange]) -> None:
        key = tuple(sorted(f"{item.action}:{item.event_id}" for item in combo))
        if key in used_pairs:
            return
        events = [item.event_id for item in combo]
        if len(events) != len(set(events)):
            return
        used_pairs.add(key)
        results.append(combo)

    for first in ranked:
        add([first])
        if max_changes < 2:
            continue
        for second in ranked:
            add([first, second])
            if max_changes < 3:
                continue
            for third in ranked:
                add([first, second, third])
    return results
