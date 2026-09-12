from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Optional

from src.models.domain import Message
from src.models.evidence import MessageExtraction

CURRENCY = r"(INR|ZAR|IDR|USD|EUR)"
AMOUNT = r"([0-9]+(?:[.,][0-9]+)?)"
ISO_DATE = r"(\d{4}-\d{2}-\d{2})"


def _dec(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def _fact(
    message: Message,
    fact_type: str,
    *,
    amount: Optional[Decimal] = None,
    secondary: Optional[Decimal] = None,
    currency: Optional[str] = None,
    effective: Optional[date] = None,
    applies_once: bool = False,
    confirmed: bool = False,
    ignore: bool = False,
    description: str = "",
) -> MessageExtraction:
    return MessageExtraction(
        message_id=message.message_id,
        fact_type=fact_type,
        related_event_id=message.related_event_id,
        amount=amount,
        secondary_amount=secondary,
        currency=currency,
        effective_date=effective,
        applies_once=applies_once,
        confirmed=confirmed,
        description=description,
        confidence=0.85,
        ignore_as_income=ignore,
    )


def parse_message(message: Message) -> list[MessageExtraction]:
    text = message.message_text
    facts: list[MessageExtraction] = []

    if re.search(r"between your two accounts|kedua akun|internal transfer", text, re.I):
        return [_fact(message, "internal_transfer", ignore=True, description="internal transfer")]
    if re.search(r"no units have been sold|no cash proceeds|unrealized|nilai pasar|displayed market value", text, re.I):
        return [_fact(message, "unrealized_gain", ignore=True, description="unrealized market value")]
    if re.search(r"refund has been initiated but has not reached|belum masuk ke akun|refund is still processing", text, re.I):
        return [_fact(message, "refund_pending", ignore=True, description="refund not settled")]
    if re.search(r"cash prize|release charge|klaim sekarang ditutup", text, re.I) and re.search(
        r"pay the release|selected for a cash prize|congratulations", text, re.I
    ):
        return [_fact(message, "prize_scam", ignore=True, description="unconfirmed prize")]
    if re.search(r"prize proceeds have reached your account", text, re.I):
        return [_fact(message, "prize_settled", confirmed=True, description="prize already settled")]
    if re.search(
        r"proceeds from your investment sale have settled|hasil penjualan investasi Anda sudah masuk|sale order is complete",
        text,
        re.I,
    ):
        return [_fact(message, "sale_settled", confirmed=True, description="investment sale settled")]
    if re.search(r"reimbursement for your earlier work expense|claim is now closed", text, re.I):
        return [_fact(message, "reimbursement_closed", ignore=True, description="no extra reimbursement")]
    if re.search(
        r"seasonal contract has ended|kontrak musiman telah berakhir|no off-season income|kontrak musiman saat ini telah berakhir",
        text,
        re.I,
    ):
        return [_fact(message, "contract_ended", description="contract ended, no confirmed renewal")]
    if re.search(
        r"your employment has ended|hubungan kerja Anda telah berakhir|there are no regular salary payments|tidak ada pembayaran gaji rutin",
        text,
        re.I,
    ):
        return [_fact(message, "contract_ended", description="employment ended")]
    if re.search(
        r"still pending|masih menunggu|not been credited|belum disetujui|can change until|masih tertunda|masih dapat berubah|have not been approved|belum disetujui|still subject to the final",
        text,
        re.I,
    ) and re.search(
        r"bonus|commission|komisi|payout|prize|invoice|faktur|weekly|mingguan|penghasilan",
        text,
        re.I,
    ):
        return [_fact(message, "unconfirmed_income", ignore=True, description="unconfirmed inbound cash")]

    date_match = re.search(ISO_DATE, text)
    effective = date.fromisoformat(date_match.group(1)) if date_match else None

    remaining = re.search(
        rf"(?:remaining confirmed monthly salary is|sisa gaji bulanan yang dikonfirmasi adalah)\s+{CURRENCY}\s+{AMOUNT}",
        text,
        re.I,
    )
    if remaining:
        facts.append(
            _fact(
                message,
                "salary_amount_update",
                amount=_dec(remaining.group(2)),
                currency=remaining.group(1).upper(),
                effective=effective,
                confirmed=True,
                description="remaining confirmed salary",
            )
        )
        if re.search(r"employment record has ended|sumber pendapatan kerja rumah tangga telah berakhir", text, re.I):
            facts.append(_fact(message, "income_source_ended", description="ended household income removed"))
        return facts

    inc = re.search(
        rf"(?:increased to|naik menjadi|has increased to)\s+{CURRENCY}\s+{AMOUNT}",
        text,
        re.I,
    )
    if inc:
        return [
            _fact(
                message,
                "salary_amount_update",
                amount=_dec(inc.group(2)),
                currency=inc.group(1).upper(),
                effective=effective,
                confirmed=True,
                description="confirmed salary increase",
            )
        ]

    temp = re.search(
        rf"(?:temporary monthly pay is|next salary is reduced to|gaji .*dikurangi menjadi|gaji bulanan sementara Anda adalah|temporary monthly pay)\s+{CURRENCY}\s+{AMOUNT}",
        text,
        re.I,
    )
    if temp:
        return [
            _fact(
                message,
                "temporary_pay",
                amount=_dec(temp.group(2)),
                currency=temp.group(1).upper(),
                effective=effective,
                applies_once=True,
                confirmed=True,
                description="temporary reduced pay",
            )
        ]

    first = re.search(
        rf"(?:first salary will be|gaji pertama Anda adalah|first salary from the new employer is|gaji pertama dari perusahaan baru adalah|first salary of|gaji pertama Anda sebesar)\s+{CURRENCY}\s+{AMOUNT}",
        text,
        re.I,
    )
    if first:
        return [
            _fact(
                message,
                "salary_amount_update",
                amount=_dec(first.group(2)),
                currency=first.group(1).upper(),
                effective=effective,
                confirmed=True,
                description="first confirmed salary",
            )
        ]

    confirmed_amt = re.search(
        rf"(?:your salary of|gaji sebesar)\s+{CURRENCY}\s+{AMOUNT}\s+(?:is confirmed|dikonfirmasi)",
        text,
        re.I,
    )
    if confirmed_amt:
        return [
            _fact(
                message,
                "salary_amount_update",
                amount=_dec(confirmed_amt.group(2)),
                currency=confirmed_amt.group(1).upper(),
                effective=effective,
                confirmed=True,
                description="confirmed salary payment",
            )
        ]

    regular = re.search(
        rf"(?:regular salary(?: for the next payroll)?(?: is| of)?|gaji rutin(?: Anda)?(?: untuk penggajian berikutnya)?(?: adalah)?)\s+{CURRENCY}\s+{AMOUNT}",
        text,
        re.I,
    )
    arrears = re.search(rf"(?:arrears adjustment of|tunggakan satu kali sebesar)\s+{CURRENCY}\s+{AMOUNT}", text, re.I)
    if regular:
        facts.append(
            _fact(
                message,
                "salary_amount_update",
                amount=_dec(regular.group(2)),
                currency=regular.group(1).upper(),
                effective=effective,
                confirmed=True,
                description="confirmed regular salary",
            )
        )
        if arrears:
            facts.append(
                _fact(
                    message,
                    "one_time_adjustment",
                    amount=_dec(arrears.group(2)),
                    currency=arrears.group(1).upper(),
                    effective=effective,
                    applies_once=True,
                    confirmed=True,
                    description="confirmed one-time arrears",
                )
            )
        return facts

    if re.search(r"gaji rutin untuk penggajian berikutnya sudah dikonfirmasi|regular salary.*confirmed", text, re.I):
        return [
            _fact(
                message,
                "salary_confirmed",
                effective=effective,
                confirmed=True,
                description="regular salary confirmed",
            )
        ]

    date_only = re.search(rf"(?:expected on|berlaku mulai|credit date is|confirmed for|dikonfirmasi untuk)\s+{ISO_DATE}", text, re.I)
    if date_only and re.search(r"salary|gaji|payroll", text, re.I):
        return [
            _fact(
                message,
                "salary_date_update",
                effective=date.fromisoformat(date_only.group(1)),
                confirmed=True,
                description="salary date amendment",
            )
        ]

    rent = re.search(r"increases monthly rent by\s+([0-9]+(?:\.[0-9]+)?)%", text, re.I)
    if rent:
        return [
            _fact(
                message,
                "rent_change",
                amount=Decimal(rent.group(1)),
                confirmed=True,
                description="rent percentage increase",
            )
        ]

    invoice = re.search(rf"(?:invoice payment of|pembayaran faktur sebesar)\s+{CURRENCY}\s+{AMOUNT}", text, re.I)
    if invoice and re.search(r"approved|menyetujui", text, re.I):
        return [
            _fact(
                message,
                "unconfirmed_income",
                amount=_dec(invoice.group(2)),
                currency=invoice.group(1).upper(),
                effective=effective,
                ignore=True,
                description="invoice not settled yet",
            )
        ]

    if re.search(r"previous debit attempt failed|bill is still outstanding|another debit will be attempted", text, re.I):
        return [_fact(message, "debit_retry", description="outstanding bill will be retried")]

    return facts
