from __future__ import annotations

from datetime import date

from src.domain.policies.user_prefs import considers, installment_months_allowed
from src.models.domain import PaymentOption, Request, UserProfile


def option_duration_months(option: PaymentOption) -> float:
    if option.number_of_payments <= 1 or not option.payment_frequency_days:
        return 1.0
    span_days = (option.number_of_payments - 1) * option.payment_frequency_days
    return span_days / 30.0 + 1.0


def option_eligible(option: PaymentOption, request: Request, profile: UserProfile) -> bool:
    if option.payment_method == "full_payment":
        return considers(profile, "full_payment")
    if option.payment_method == "installments":
        if not considers(profile, "installments"):
            return False
        return installment_months_allowed(profile, option_duration_months(option))
    return False


def last_option_date(option: PaymentOption) -> date:
    if option.number_of_payments <= 1 or not option.payment_frequency_days:
        return option.first_payment_date
    delta = option.payment_frequency_days * (option.number_of_payments - 1)
    return option.first_payment_date.fromordinal(
        option.first_payment_date.toordinal() + delta
    )
