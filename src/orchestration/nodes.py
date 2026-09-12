from __future__ import annotations

from datetime import timedelta

from src.agents.explanation_agent import generate_explanation
from src.agents.message_agent import extract_message_facts
from src.models.evidence import ConflictRecord
from src.agents.vision_agent import extract_image_amount
from src.data.repositories import Repository
from src.domain.decisions.builder import build_decision
from src.domain.finance.cashflow import (
    build_forecast,
    earliest_full_payment_date,
)
from src.domain.finance.safe_today import amount_safe_to_pay_today, next_confirmed_salary_date
from src.domain.finance.state_builder import build_financial_state
from src.domain.payments.planner import generate_plans
from src.domain.payments.ranker import rank_plans
from src.domain.payments.validator import validate_plans
from src.domain.policies.spending_policy import change_combinations, eligible_changes
from src.infrastructure.config import get_settings
from src.orchestration.state import BuyWaitState


def validate_request(state: BuyWaitState) -> BuyWaitState:
    request = state["request"]
    errors = list(state.get("errors") or [])
    if request.requested_amount < 0:
        errors.append("requested_amount_negative")
    return {**state, "errors": errors, "uncertainties": list(state.get("uncertainties") or [])}


def load_context(state: BuyWaitState, repository: Repository) -> BuyWaitState:
    request = state["request"]
    profile = repository.get_user_profile(request.user_id)
    return {
        **state,
        "profile": profile,
        "events": repository.get_user_events(request.user_id),
        "messages": repository.user_messages(request.user_id),
        "images": repository.user_images(request.user_id),
        "payment_options": repository.get_payment_options(request.request_id),
    }


def extract_image_amounts(state: BuyWaitState, repository: Repository) -> BuyWaitState:
    if state.get("image_facts") is not None:
        return state
    facts = []
    uncertainties = list(state.get("uncertainties") or [])
    for image in state.get("images") or []:
        event = repository.get_event(image.related_event_id) if image.related_event_id else None
        extraction = extract_image_amount(image, event)
        facts.append(extraction)
        if extraction.amount is None:
            uncertainties.append(f"missing_image_amount:{image.image_id}")
    return {**state, "image_facts": facts, "uncertainties": uncertainties}


def extract_message_facts_node(state: BuyWaitState) -> BuyWaitState:
    if state.get("message_facts") is not None:
        return state
    facts = []
    for message in state.get("messages") or []:
        facts.extend(extract_message_facts(message))
    return {**state, "message_facts": facts}


def reconcile_evidence(state: BuyWaitState) -> BuyWaitState:
    facts = state.get("message_facts") or []
    conflicts = list(state.get("conflicts") or [])
    unconfirmed = [fact for fact in facts if fact.ignore_as_income or fact.fact_type == "unconfirmed_income"]
    if unconfirmed:
        conflicts.append(
            ConflictRecord(
                topic="unconfirmed_income",
                resolution="ignore_unconfirmed_credits",
                safer_choice="do_not_count_until_settled",
                sources=[item.message_id for item in unconfirmed if getattr(item, "message_id", None)],
                auto_resolved=True,
            )
        )
    return {**state, "conflicts": conflicts}


def build_financial_state_node(state: BuyWaitState, repository: Repository) -> BuyWaitState:
    financial_state = build_financial_state(
        state["request"],
        state["profile"],
        repository,
        state.get("image_facts") or [],
        state.get("message_facts") or [],
    )
    return {**state, "financial_state": financial_state}


def run_forecast(state: BuyWaitState) -> BuyWaitState:
    settings = get_settings()
    financial_state = state["financial_state"]
    request = state["request"]
    base_forecast = build_forecast(financial_state, settings.forecast_days)
    safe_today = amount_safe_to_pay_today(
        financial_state,
        base_forecast,
        request.requested_amount,
        request.request_date,
    )
    earliest = earliest_full_payment_date(
        base_forecast, request.requested_amount, request.request_date
    )
    if safe_today >= request.requested_amount:
        earliest = request.request_date
    elif (
        earliest == request.request_date
        and safe_today < request.requested_amount
    ):
        nxt = next_confirmed_salary_date(financial_state)
        if nxt is not None and nxt > request.request_date:
            earliest = nxt
        else:
            earliest = request.request_date + timedelta(days=1)
    return {
        **state,
        "forecast": base_forecast,
        "amount_safe_to_pay": safe_today,
        "earliest_date": earliest,
    }


def generate_and_rank_plans(state: BuyWaitState) -> BuyWaitState:
    settings = get_settings()
    request = state["request"]
    profile = state["profile"]
    financial_state = state["financial_state"]
    options = state.get("payment_options") or []
    candidates = generate_plans(
        request,
        profile,
        options,
        state["amount_safe_to_pay"],
        state.get("earliest_date"),
        [],
    )
    valid = validate_plans(financial_state, candidates, settings.forecast_days)

    if not any(plan.completes_by_deadline for plan in valid):
        eligible = eligible_changes(profile, financial_state.recurring)
        eligible = eligible[:10]
        for combo in change_combinations(eligible, max_changes=2)[1:]:
            changed_forecast = build_forecast(financial_state, settings.forecast_days, combo)
            changed_safe = amount_safe_to_pay_today(
                financial_state,
                changed_forecast,
                request.requested_amount,
                request.request_date,
                combo,
            )
            changed_earliest = earliest_full_payment_date(
                changed_forecast, request.requested_amount, request.request_date
            )
            extra = generate_plans(
                request, profile, options, changed_safe, changed_earliest, combo
            )
            valid.extend(validate_plans(financial_state, extra, settings.forecast_days))
            if any(plan.completes_by_deadline for plan in valid):
                break

    ranked = rank_plans(valid)
    selected = ranked[0] if ranked else None
    return {
        **state,
        "candidate_plans": candidates,
        "valid_plans": ranked,
        "selected_plan": selected,
    }


def build_decision_node(state: BuyWaitState) -> BuyWaitState:
    explanation = generate_explanation(
        state["request"],
        state["profile"],
        state.get("selected_plan"),
        state.get("earliest_date"),
        use_llm=bool(state.get("use_llm_explanation", False)),
    )
    decision = build_decision(
        state["request"],
        state["profile"],
        state["amount_safe_to_pay"],
        state.get("earliest_date"),
        state.get("selected_plan"),
        explanation,
    )
    return {**state, "decision": decision}
