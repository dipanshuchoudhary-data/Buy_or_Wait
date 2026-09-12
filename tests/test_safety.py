from datetime import date
from decimal import Decimal

from src.domain.finance.cashflow import is_safe, project
from src.models.financial import CashflowForecast, CashflowItem
from src.models.output import PlanPayment


def _forecast() -> CashflowForecast:
    return CashflowForecast(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        opening_balance=Decimal("1000"),
        minimum_balance=Decimal("400"),
        currency="USD",
        items=[CashflowItem(on=date(2026, 1, 5), amount=Decimal("-200"), label="bill")],
    )


def test_unsafe_payment_is_rejected() -> None:
    forecast = _forecast()
    assert is_safe(forecast, [PlanPayment(on=date(2026, 1, 1), amount=Decimal("400"))])
    assert not is_safe(forecast, [PlanPayment(on=date(2026, 1, 1), amount=Decimal("500"))])


def test_trough_tracks_minimum() -> None:
    projection = project(_forecast(), [PlanPayment(on=date(2026, 1, 1), amount=Decimal("300"))])
    assert projection.trough == Decimal("500.00")
