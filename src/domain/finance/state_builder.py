from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from src.data.repositories import Repository
from src.domain.finance.currency import CurrencyConverter
from src.domain.finance.events import apply_image_amounts, apply_message_overrides, normalize_events
from src.domain.finance.recurrence import detect_recurring_patterns, residual_monthly_spend
from src.models.domain import Request, UserProfile
from src.models.evidence import ImageExtraction, MessageExtraction
from src.models.financial import FinancialState


def _salary_override(facts: list[MessageExtraction], as_of: date) -> tuple[Optional[Decimal], Optional[date], bool]:
    amount = None
    start = None
    contract_ended = False
    temporary = None
    for fact in facts:
        if fact.fact_type == "contract_ended":
            contract_ended = True
        if fact.fact_type == "salary_amount_update" and fact.amount is not None:
            amount = fact.amount
            start = fact.effective_date
        if fact.fact_type == "temporary_pay" and fact.amount is not None:
            temporary = (fact.amount, fact.effective_date or as_of)
    if temporary and amount is None:
        return temporary[0], temporary[1], contract_ended
    return amount, start, contract_ended


def build_financial_state(
    request: Request,
    profile: UserProfile,
    repository: Repository,
    image_facts: list[ImageExtraction],
    message_facts: list[MessageExtraction],
) -> FinancialState:
    converter = CurrencyConverter(repository)
    events = repository.get_user_events(profile.user_id)
    events = apply_image_amounts(events, image_facts)
    events = apply_message_overrides(events, message_facts, request.request_date)
    salary_amount, salary_from, contract_ended = _salary_override(
        message_facts, request.request_date
    )
    normalized = normalize_events(
        events,
        profile,
        converter,
        request.request_date,
        salary_amount_override=salary_amount,
        salary_override_from=salary_from,
    )
    if contract_ended:
        for event in normalized:
            if (
                event.event_type == "income"
                and event.category == "salary"
                and event.status == "scheduled"
                and event.settlement_date >= request.request_date
            ):
                event.include_in_forecast = False
    recurring = detect_recurring_patterns(normalized, request.request_date)
    if contract_ended:
        recurring = [
            item
            for item in recurring
            if not (item.event_type == "income" and item.category == "salary")
        ]
    blocked = (
        "commission",
        "bonus",
        "prize",
        "lottery",
        "invoice",
        "reimbursement",
        "refund",
        "gig",
        "weekly",
    )
    recurring = [
        item
        for item in recurring
        if not (
            item.direction == "credit"
            and any(token in item.description.lower() for token in blocked)
        )
    ]
    if salary_amount is not None:
        for item in recurring:
            if item.event_type == "income" and item.category == "salary":
                converted = converter.try_convert(
                    salary_amount,
                    profile.home_currency,
                    profile.home_currency,
                    item.next_date,
                )
                if converted is not None:
                    item.amount_home = converted
    residual = residual_monthly_spend(
        normalized, recurring, request.request_date, profile.expense_categories_to_protect
    )
    return FinancialState(
        user_id=profile.user_id,
        as_of=request.request_date,
        currency=profile.home_currency,
        opening_balance=profile.current_available_balance,
        minimum_balance=profile.minimum_balance_to_keep,
        events=normalized,
        recurring=recurring,
        residual_monthly=residual,
    )
