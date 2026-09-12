from __future__ import annotations

from src.models.output import CandidatePlan


def rank_plans(plans: list[CandidatePlan]) -> list[CandidatePlan]:
    def key(plan: CandidatePlan) -> tuple:
        option_id = plan.payment_option_id or "zzzz"
        return (
            0 if plan.completes_by_deadline else 1,
            0 if not plan.spending_changes else 1,
            plan.total_paid,
            plan.start_date.toordinal() if plan.start_date else 10**9,
            len(plan.payments),
            option_id,
        )

    return sorted(plans, key=key)
