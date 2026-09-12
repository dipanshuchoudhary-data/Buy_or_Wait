from datetime import datetime, timezone
from decimal import Decimal

from src.agents.message_rules import parse_message
from src.models.domain import Message


def _msg(text: str, message_id: str = "message_x") -> Message:
    return Message(
        message_id=message_id,
        user_id="user_x",
        sent_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_type="employer",
        message_text=text,
    )


def test_temporary_pay_english() -> None:
    facts = parse_message(_msg("Your temporary monthly pay is EUR 1037.52. The reduced amount continues."))
    assert facts[0].fact_type == "temporary_pay"
    assert facts[0].amount == Decimal("1037.52")


def test_temporary_pay_indonesian() -> None:
    facts = parse_message(_msg("Gaji bulanan sementara Anda adalah IDR 31464000. Jumlah yang lebih rendah masih berlaku."))
    assert facts[0].fact_type == "temporary_pay"
    assert facts[0].amount == Decimal("31464000")


def test_unconfirmed_bonus_is_ignored() -> None:
    facts = parse_message(
        _msg("Your quarterly bonus is still subject to the final performance review. The final amount and payment date have not been approved.")
    )
    assert facts[0].ignore_as_income is True


def test_employment_ended() -> None:
    facts = parse_message(_msg("Your employment has ended. There are no regular salary payments scheduled after the final settlement."))
    assert facts[0].fact_type == "contract_ended"


def test_remaining_household_salary() -> None:
    facts = parse_message(
        _msg("One household employment record has ended. The remaining confirmed monthly salary is INR 148000.")
    )
    assert any(fact.fact_type == "salary_amount_update" and fact.amount == Decimal("148000") for fact in facts)


def test_prize_scam_ignored() -> None:
    facts = parse_message(_msg("Congratulations! You've been selected for a cash prize. Pay the release charge today."))
    assert facts[0].ignore_as_income is True


def test_unrealized_market_value_ignored() -> None:
    facts = parse_message(_msg("Your portfolio's displayed market value has increased substantially."))
    assert facts[0].ignore_as_income is True
