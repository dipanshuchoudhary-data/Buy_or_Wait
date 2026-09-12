from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.infrastructure.llm import invoke_text
from src.infrastructure.logging import get_logger
from src.models.domain import Request, UserProfile
from src.models.output import CandidatePlan, RecommendedMethod
from src.prompts import explanation_prompts

logger = get_logger("explain")


def _fmt_money(currency: str, amount: Decimal) -> str:
    quantized = amount.quantize(Decimal("0.01"))
    text = f"{quantized:,.2f}".rstrip("0").rstrip(".")
    return f"{currency} {text}"


def template_explanation(
    request: Request,
    profile: UserProfile,
    selected: CandidatePlan | None,
    earliest: date | None,
) -> str:
    currency = profile.home_currency
    minimum = _fmt_money(currency, profile.minimum_balance_to_keep)
    requested = _fmt_money(currency, request.requested_amount)
    if selected is None:
        return (
            f"Do not make this payment by {request.desired_completion_date.isoformat()}. "
            f"None of the available options keeps the {minimum} minimum protected."
        )
    if selected.method == RecommendedMethod.FULL_PAYMENT:
        prefix = ""
        if selected.spending_changes:
            prefix = "After the permitted spending changes, "
        return (
            f"{prefix}Pay {requested} today. This leaves at least {minimum} "
            "available over the next 90 days."
        )
    if selected.method == RecommendedMethod.INSTALLMENTS and selected.payments:
        first = selected.payments[0]
        return (
            f"Use {len(selected.payments)} installments of {_fmt_money(currency, first.amount)}, "
            f"starting {first.on.strftime('%d %B %Y').lstrip('0')}. This leaves at least {minimum} available."
        )
    if selected.method == RecommendedMethod.PARTIAL_PAYMENT and len(selected.payments) == 2:
        first, second = selected.payments
        return (
            f"Pay {_fmt_money(currency, first.amount)} today and the remaining "
            f"{_fmt_money(currency, second.amount)} on {second.on.isoformat()}. "
            f"Today is limited to cash on hand after bills due before the next confirmed income. "
            f"This completes the full request and keeps the {minimum} minimum protected."
        )
    if selected.method == RecommendedMethod.WAIT and selected.payments:
        when = selected.payments[0].on
        return (
            f"Wait until {when.isoformat()}, then pay {requested} in full. "
            f"Paying sooner would put the {minimum} minimum at risk."
        )
    return (
        f"Do not proceed with the {requested} request. Although some funds are available today, "
        "the full amount cannot be completed safely within 90 days."
    )


def generate_explanation(
    request: Request,
    profile: UserProfile,
    selected: CandidatePlan | None,
    earliest: date | None,
    use_llm: bool = False,
) -> str:
    fallback = template_explanation(request, profile, selected, earliest)
    if not use_llm:
        return fallback
    payload = {
        "request_id": request.request_id,
        "currency": profile.home_currency,
        "requested_amount": str(request.requested_amount),
        "minimum_balance": str(profile.minimum_balance_to_keep),
        "method": selected.method.value if selected else "not_recommended",
        "payments": [
            {"on": item.on.isoformat(), "amount": str(item.amount)}
            for item in (selected.payments if selected else [])
        ],
        "spending_changes": [
            item.render() for item in (selected.spending_changes if selected else [])
        ],
        "earliest": earliest.isoformat() if earliest else "",
        "template": fallback,
    }
    try:
        result = invoke_text(explanation_prompts.SYSTEM_PROMPT, explanation_prompts.user_prompt(str(payload)))
        text = str(result.get("explanation") or "").strip()
        return text or fallback
    except Exception as exc:
        logger.warning("explanation model failed for %s: %s", request.request_id, exc)
        return fallback
