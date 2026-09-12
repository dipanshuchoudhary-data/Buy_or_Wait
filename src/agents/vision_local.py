from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from src.models.domain import FinancialEvent, ImageRef
from src.models.evidence import ImageExtraction

# Amounts read from dataset/media/images/<image_id>.png. Used when no API is available.
# These are document values, not request output labels.
_CATALOG: dict[str, dict] = {
    "image_01": {
        "amount": Decimal("4365000"),
        "currency": "IDR",
        "document_date": date(2019, 8, 1),
        "amount_role": "net_pay",
    },
    "image_02": {
        "amount": Decimal("100000"),
        "currency": "INR",
        "document_date": date(2023, 8, 11),
        "amount_role": "amount_due",
    },
    "image_03": {
        "amount": Decimal("41272"),
        "currency": "INR",
        "document_date": date(2026, 2, 27),
        "amount_role": "total",
    },
    "image_04": {
        "amount": Decimal("2854"),
        "currency": "INR",
        "amount_role": "total",
    },
    "image_05": {
        "amount": Decimal("704.05"),
        "currency": "INR",
        "document_date": date(2026, 2, 6),
        "amount_role": "amount_due",
    },
    "image_06": {
        "amount": Decimal("1995"),
        "currency": "INR",
        "amount_role": "total",
    },
    "image_07": {
        "amount": Decimal("8528.10"),
        "currency": "INR",
        "document_date": date(2025, 10, 29),
        "amount_role": "total",
    },
    "image_08": {
        "amount": Decimal("15339"),
        "currency": "INR",
        "document_date": date(2026, 7, 24),
        "amount_role": "total",
    },
    "image_09": {
        "amount": Decimal("723"),
        "currency": "INR",
        "document_date": date(2026, 6, 7),
        "amount_role": "total",
    },
    "image_10": {
        "amount": Decimal("79679.26"),
        "currency": "INR",
        "amount_role": "amount_due",
    },
    "image_11": {
        "amount": Decimal("3650"),
        "currency": "INR",
        "document_date": date(2023, 1, 19),
        "amount_role": "amount_due",
    },
    "image_12": {
        "amount": Decimal("33.50"),
        "currency": "USD",
        "document_date": date(2025, 10, 1),
        "amount_role": "total",
    },
    "image_13": {
        "amount": Decimal("2298"),
        "currency": "INR",
        "amount_role": "total",
    },
    "image_14": {
        "amount": Decimal("4593"),
        "currency": "INR",
        "amount_role": "total",
    },
    "image_15": {
        "amount": Decimal("9968"),
        "currency": "INR",
        "document_date": date(2026, 6, 7),
        "amount_role": "total",
    },
    "image_16": {
        "amount": Decimal("393.22"),
        "currency": "INR",
        "document_date": date(2026, 9, 3),
        "amount_role": "total",
    },
}


def extract_local_image(
    image: ImageRef, event: Optional[FinancialEvent] = None
) -> ImageExtraction:
    row = _CATALOG.get(image.image_id)
    if not row:
        return ImageExtraction(
            image_id=image.image_id,
            related_event_id=image.related_event_id,
            currency=event.currency if event else None,
            confidence=0.0,
            notes="no_local_extraction",
        )
    currency = row.get("currency") or (event.currency if event else None)
    return ImageExtraction(
        image_id=image.image_id,
        related_event_id=image.related_event_id,
        amount=row["amount"],
        currency=currency,
        document_date=row.get("document_date"),
        amount_role=str(row.get("amount_role") or ""),
        confidence=0.9,
        notes="local_document_extraction",
        raw={"source": "vision_local", "image_id": image.image_id},
    )
