from __future__ import annotations

from src.models.domain import UserProfile


def considers(profile: UserProfile, method: str) -> bool:
    return method in profile.payment_methods_user_will_consider


def installment_months_allowed(profile: UserProfile, months: float) -> bool:
    if profile.max_installment_months is None:
        return False
    return months <= profile.max_installment_months + 0.01
