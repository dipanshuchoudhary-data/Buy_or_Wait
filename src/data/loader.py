from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from src.infrastructure.config import get_settings
from src.models.domain import (
    ExchangeRate,
    FinancialEvent,
    ImageRef,
    Message,
    PaymentOption,
    Request,
    UserProfile,
)


def _split_pipe(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def _decimal(value: object) -> Optional[Decimal]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _date(value: object, fallback: object | None = None) -> date:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        if fallback is None:
            raise ValueError("missing date")
        return _date(fallback)
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        if fallback is None:
            raise ValueError(f"invalid date: {value!r}")
        return _date(fallback)
    return parsed.date()


def _optional_date(value: object) -> Optional[date]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return pd.to_datetime(value).date()


def _datetime(value: object) -> datetime:
    parsed = pd.to_datetime(value, utc=True)
    return parsed.to_pydatetime()


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def _optional_int(value: object) -> Optional[int]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return int(float(text))


def _optional_str(value: object) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


@lru_cache(maxsize=1)
def load_dataset(dataset_dir: Optional[str] = None) -> "Dataset":
    settings = get_settings()
    root = Path(dataset_dir) if dataset_dir else settings.dataset_dir
    return Dataset(root)


class Dataset:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.profiles = self._load_profiles(root / "financial_profiles.csv")
        self.events = self._load_events(root / "financial_events.csv")
        self.rates = self._load_rates(root / "exchange_rates.csv")
        self.requests = self._load_requests(root / "requests.csv")
        self.sample_requests = self._load_requests(root / "sample_requests.csv")
        self.payment_options = self._load_options(root / "request_payment_options.csv")
        self.messages = self._load_messages(root / "messages.csv")
        self.images = self._load_images(root / "images.csv", root / "media" / "images")

    def _load_profiles(self, path: Path) -> dict[str, UserProfile]:
        frame = pd.read_csv(path)
        profiles: dict[str, UserProfile] = {}
        for row in frame.itertuples(index=False):
            profile = UserProfile(
                user_id=str(row.user_id),
                home_currency=str(row.home_currency),
                current_available_balance=_decimal(row.current_available_balance) or Decimal("0"),
                minimum_balance_to_keep=_decimal(row.minimum_balance_to_keep) or Decimal("0"),
                financial_priorities=_split_pipe(row.financial_priorities),
                expense_categories_to_protect=_split_pipe(row.expense_categories_to_protect),
                expense_categories_user_is_willing_to_reduce=_split_pipe(
                    row.expense_categories_user_is_willing_to_reduce
                ),
                expense_categories_user_is_willing_to_stop=_split_pipe(
                    row.expense_categories_user_is_willing_to_stop
                ),
                payment_methods_user_will_consider=_split_pipe(
                    row.payment_methods_user_will_consider
                ),
                max_installment_months=_optional_int(row.max_installment_months),
            )
            profiles[profile.user_id] = profile
        return profiles

    def _load_events(self, path: Path) -> dict[str, list[FinancialEvent]]:
        frame = pd.read_csv(path)
        grouped: dict[str, list[FinancialEvent]] = {}
        for row in frame.to_dict(orient="records"):
            event = FinancialEvent(
                event_id=str(row["event_id"]),
                user_id=str(row["user_id"]),
                event_type=str(row["event_type"]),
                description=str(row["description"]),
                category=str(row["category"]),
                direction=str(row["direction"]),
                amount=_decimal(row["amount"]),
                currency=str(row["currency"]),
                event_date=_date(row["event_date"]),
                settlement_date=_date(row["settlement_date"], fallback=row["event_date"]),
                status=str(row["status"]),
                linked_event_id=_optional_str(row["linked_event_id"]),
                flexibility=str(row["flexibility"]) if row.get("flexibility") == row.get("flexibility") else "fixed",
                minimum_allowed_amount=_decimal(row["minimum_allowed_amount"]),
            )
            grouped.setdefault(event.user_id, []).append(event)
        return grouped

    def _load_rates(self, path: Path) -> list[ExchangeRate]:
        frame = pd.read_csv(path)
        rates: list[ExchangeRate] = []
        for row in frame.itertuples(index=False):
            rates.append(
                ExchangeRate(
                    rate_date=_date(row.rate_date),
                    from_currency=str(row.from_currency),
                    to_currency=str(row.to_currency),
                    rate=_decimal(row.rate) or Decimal("0"),
                )
            )
        return rates

    def _load_requests(self, path: Path) -> list[Request]:
        frame = pd.read_csv(path)
        requests: list[Request] = []
        for row in frame.itertuples(index=False):
            requests.append(
                Request(
                    request_id=str(row.request_id),
                    user_id=str(row.user_id),
                    request_date=_date(row.request_date),
                    request_type=row.request_type,
                    requested_amount=_decimal(row.requested_amount) or Decimal("0"),
                    desired_completion_date=_date(row.desired_completion_date),
                    allows_partial_payment=_bool(row.allows_partial_payment),
                    request_text=str(getattr(row, "request_text", "") or ""),
                )
            )
        return requests

    def _load_options(self, path: Path) -> dict[str, list[PaymentOption]]:
        frame = pd.read_csv(path)
        grouped: dict[str, list[PaymentOption]] = {}
        for row in frame.itertuples(index=False):
            option = PaymentOption(
                payment_option_id=str(row.payment_option_id),
                request_id=str(row.request_id),
                payment_method=str(row.payment_method),
                payment_amount=_decimal(row.payment_amount) or Decimal("0"),
                number_of_payments=int(row.number_of_payments),
                first_payment_date=_date(row.first_payment_date),
                payment_frequency_days=_optional_int(row.payment_frequency_days),
                financing_fee=_decimal(row.financing_fee) or Decimal("0"),
                total_payable_amount=_decimal(row.total_payable_amount) or Decimal("0"),
            )
            grouped.setdefault(option.request_id, []).append(option)
        return grouped

    def _load_messages(self, path: Path) -> list[Message]:
        frame = pd.read_csv(path)
        messages: list[Message] = []
        for row in frame.itertuples(index=False):
            messages.append(
                Message(
                    message_id=str(row.message_id),
                    user_id=str(row.user_id),
                    request_id=_optional_str(row.request_id),
                    related_event_id=_optional_str(row.related_event_id),
                    sent_at=_datetime(row.sent_at),
                    source_type=str(row.source_type),
                    message_text=str(row.message_text),
                )
            )
        return messages

    def _load_images(self, path: Path, media_dir: Path) -> list[ImageRef]:
        frame = pd.read_csv(path)
        images: list[ImageRef] = []
        for row in frame.itertuples(index=False):
            image_id = str(row.image_id)
            file_path = media_dir / f"{image_id}.png"
            images.append(
                ImageRef(
                    image_id=image_id,
                    user_id=str(row.user_id),
                    request_id=_optional_str(row.request_id),
                    related_event_id=_optional_str(row.related_event_id),
                    path=str(file_path) if file_path.exists() else None,
                )
            )
        return images
