from datetime import date
from decimal import Decimal

from src.domain.finance.currency import CurrencyConverter


class _RateRepo:
    def get_exchange_rate(self, rate_date, from_currency, to_currency):
        if from_currency == to_currency:
            return Decimal("1")
        if from_currency == "USD" and to_currency == "IDR" and rate_date == date(2023, 10, 15):
            return Decimal("15833.33")
        return None


def test_same_currency_is_identity() -> None:
    converter = CurrencyConverter(_RateRepo())
    assert converter.convert(Decimal("10"), "INR", "INR", date(2024, 1, 1)) == Decimal("10")


def test_known_usd_idr_rate() -> None:
    converter = CurrencyConverter(_RateRepo())
    result = converter.convert(Decimal("1800"), "USD", "IDR", date(2023, 10, 15))
    assert result == Decimal("1800") * Decimal("15833.33")


def test_missing_rate_returns_none() -> None:
    converter = CurrencyConverter(_RateRepo())
    assert converter.try_convert(Decimal("10"), "EUR", "INR", date(2024, 1, 1)) is None
