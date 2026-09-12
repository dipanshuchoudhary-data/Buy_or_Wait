from __future__ import annotations

from src.domain.finance.cashflow import project
from src.models.financial import CashflowForecast
from src.models.output import CandidatePlan


def evaluate_plan(forecast: CashflowForecast, plan: CandidatePlan) -> CandidatePlan:
    projection = project(forecast, plan.payments)
    plan.safe = projection.safe
    plan.trough = projection.trough
    return plan
