from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from src.domain.finance.currency import CurrencyConverter
from src.models.domain import EventStatus, FinancialEvent, UserProfile
from src.models.evidence import ImageExtraction, MessageExtraction
from src.models.financial import NormalizedEvent


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


IGNORED_STATUSES = {"cancelled", "failed"}
UNCOUNTED_PENDING_CREDITS = {"pending"}


def apply_image_amounts(
    events: list[FinancialEvent], extractions: list[ImageExtraction]
) -> list[FinancialEvent]:
    by_event = {
        item.related_event_id: item
        for item in extractions
        if item.related_event_id and item.amount is not None
    }
    updated: list[FinancialEvent] = []
    for event in events:
        extraction = by_event.get(event.event_id)
        if event.amount is None and extraction is not None:
            event = event.model_copy(
                update={
                    "amount": extraction.amount,
                    "currency": extraction.currency or event.currency,
                }
            )
        updated.append(event)
    return updated


def apply_message_overrides(
    events: list[FinancialEvent],
    facts: list[MessageExtraction],
    as_of: date,
) -> list[FinancialEvent]:
    ignore_unconfirmed = any(fact.ignore_as_income or fact.fact_type == "unconfirmed_income" for fact in facts)
    ended = any(fact.fact_type in {"contract_ended", "income_source_ended"} for fact in facts)
    cancelled_ids = {
        fact.related_event_id
        for fact in facts
        if fact.fact_type == "cancel_event" and fact.related_event_id
    }
    date_overrides = {
        fact.related_event_id: fact.effective_date
        for fact in facts
        if fact.fact_type in {"salary_date_update", "delay_event"}
        and fact.related_event_id
        and fact.effective_date
    }
    updated: list[FinancialEvent] = []
    for event in events:
        if event.event_id in cancelled_ids:
            event = event.model_copy(update={"status": "cancelled"})
        new_date = date_overrides.get(event.event_id)
        if new_date:
            event = event.model_copy(update={"settlement_date": new_date})
        if ignore_unconfirmed and _enum_value(event.direction) == "credit" and _enum_value(event.status) in {
            "pending",
            "scheduled",
        }:
            desc = event.description.lower()
            if any(token in desc for token in ("bonus", "commission", "invoice", "prize", "refund")):
                event = event.model_copy(update={"status": EventStatus.CANCELLED})
        if ended and _enum_value(event.direction) == "credit" and _enum_value(event.status) == "scheduled":
            if "final" in event.description.lower() or "off-season" in event.description.lower():
                event = event.model_copy(update={"status": EventStatus.CANCELLED})
        updated.append(event)
    return updated


def normalize_events(
    events: list[FinancialEvent],
    profile: UserProfile,
    converter: CurrencyConverter,
    as_of: date,
    salary_amount_override: Optional[Decimal] = None,
    salary_override_from: Optional[date] = None,
) -> list[NormalizedEvent]:
    normalized: list[NormalizedEvent] = []
    for event in events:
        status = _enum_value(event.status)
        direction = _enum_value(event.direction)
        event_type = _enum_value(event.event_type)
        if status in IGNORED_STATUSES:
            continue
        if direction == "non_cash" or status == "unrealized":
            continue
        if event.amount is None:
            continue
        amount = event.amount
        if (
            event_type == "income"
            and event.category == "salary"
            and salary_amount_override is not None
            and (salary_override_from is None or event.settlement_date >= salary_override_from)
        ):
            amount = salary_amount_override
        amount_home = converter.try_convert(
            amount, event.currency, profile.home_currency, event.settlement_date
        )
        if amount_home is None:
            if event.currency == profile.home_currency:
                amount_home = amount
            else:
                continue
        already_in_balance = status == "settled" and event.settlement_date < as_of
        pending_credit = direction == "credit" and status == "pending"
        include = (not already_in_balance) and (not pending_credit)
        if status == "scheduled" and event.settlement_date >= as_of:
            include = True
        if status == "pending" and direction == "debit":
            include = True
        if status == "settled" and event.settlement_date >= as_of:
            include = True
        signed = amount_home if direction == "credit" else -amount_home
        normalized.append(
            NormalizedEvent(
                event_id=event.event_id,
                user_id=event.user_id,
                event_type=event_type,
                description=event.description,
                category=event.category,
                direction=direction,
                amount_home=signed,
                original_amount=amount,
                original_currency=event.currency,
                event_date=event.event_date,
                settlement_date=event.settlement_date,
                status=status,
                linked_event_id=event.linked_event_id,
                flexibility=event.flexibility,
                minimum_allowed_amount=event.minimum_allowed_amount,
                include_in_forecast=include,
                already_in_balance=already_in_balance,
            )
        )
    return normalized
