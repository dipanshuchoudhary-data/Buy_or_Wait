from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from src.data.loader import Dataset, load_dataset
from src.models.domain import (
    ExchangeRate,
    FinancialEvent,
    ImageRef,
    Message,
    PaymentOption,
    Request,
    UserProfile,
)


class Repository:
    def __init__(self, dataset: Optional[Dataset] = None) -> None:
        self.dataset = dataset or load_dataset()
        self._events_by_id = {
            event.event_id: event
            for events in self.dataset.events.values()
            for event in events
        }
        self._requests_by_id = {item.request_id: item for item in self.dataset.requests}
        for item in self.dataset.sample_requests:
            self._requests_by_id.setdefault(item.request_id, item)

    def get_user_profile(self, user_id: str) -> UserProfile:
        return self.dataset.profiles[user_id]

    def get_user_events(self, user_id: str) -> list[FinancialEvent]:
        return list(self.dataset.events.get(user_id, []))

    def get_event(self, event_id: str) -> Optional[FinancialEvent]:
        return self._events_by_id.get(event_id)

    def get_request(self, request_id: str) -> Request:
        return self._requests_by_id[request_id]

    def evaluation_requests(self) -> list[Request]:
        return list(self.dataset.requests)

    def sample_requests(self) -> list[Request]:
        return list(self.dataset.sample_requests)

    def get_request_messages(self, user_id: str, request_id: str) -> list[Message]:
        selected: list[Message] = []
        for message in self.dataset.messages:
            if message.user_id != user_id:
                continue
            if message.request_id in {None, request_id} or message.related_event_id:
                selected.append(message)
        return selected

    def user_messages(self, user_id: str) -> list[Message]:
        return [message for message in self.dataset.messages if message.user_id == user_id]

    def all_messages(self) -> list[Message]:
        return list(self.dataset.messages)

    def get_request_images(self, user_id: str, request_id: str) -> list[ImageRef]:
        return [
            image
            for image in self.dataset.images
            if image.user_id == user_id
            and (image.request_id in {None, request_id} or image.related_event_id)
        ]

    def user_images(self, user_id: str) -> list[ImageRef]:
        return [image for image in self.dataset.images if image.user_id == user_id]

    def all_images(self) -> list[ImageRef]:
        return list(self.dataset.images)

    def get_payment_options(self, request_id: str) -> list[PaymentOption]:
        return list(self.dataset.payment_options.get(request_id, []))

    def get_exchange_rate(
        self, rate_date: date, from_currency: str, to_currency: str
    ) -> Optional[Decimal]:
        if from_currency == to_currency:
            return Decimal("1")
        for rate in self.dataset.rates:
            if (
                rate.rate_date == rate_date
                and rate.from_currency == from_currency
                and rate.to_currency == to_currency
            ):
                return rate.rate
        return None

    def rates(self) -> list[ExchangeRate]:
        return list(self.dataset.rates)
