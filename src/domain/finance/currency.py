from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from src.data.repositories import Repository


class CurrencyConverter:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        on: date,
    ) -> Decimal:
        if from_currency == to_currency:
            return amount
        rate = self.repository.get_exchange_rate(on, from_currency, to_currency)
        if rate is None:
            raise ValueError(
                f"No exchange rate for {from_currency}->{to_currency} on {on.isoformat()}"
            )
        return amount * rate

    def try_convert(
        self,
        amount: Optional[Decimal],
        from_currency: str,
        to_currency: str,
        on: date,
    ) -> Optional[Decimal]:
        if amount is None:
            return None
        try:
            return self.convert(amount, from_currency, to_currency, on)
        except ValueError:
            return None
