from __future__ import annotations

from typing import Any, Optional, TypedDict


class BuyWaitState(TypedDict, total=False):
    request_id: str
    request: Any
    profile: Any
    events: list
    messages: list
    images: list
    payment_options: list
    image_facts: list
    message_facts: list
    conflicts: list
    financial_state: Any
    forecast: Any
    amount_safe_to_pay: Any
    earliest_date: Any
    candidate_plans: list
    valid_plans: list
    selected_plan: Any
    decision: Any
    uncertainties: list
    errors: list
    use_llm_explanation: bool
