from __future__ import annotations

from src.domain.finance.cashflow import build_forecast, is_safe
from src.domain.policies.safety import evaluate_plan
from src.models.financial import FinancialState
from src.models.output import CandidatePlan


def validate_plans(
    state: FinancialState,
    plans: list[CandidatePlan],
    horizon_days: int = 90,
) -> list[CandidatePlan]:
    validated: list[CandidatePlan] = []
    for plan in plans:
        forecast = build_forecast(state, horizon_days, plan.spending_changes)
        evaluate_plan(forecast, plan)
        if plan.safe:
            validated.append(plan)
        elif is_safe(forecast) and not plan.payments:
            validated.append(plan)
    return validated
