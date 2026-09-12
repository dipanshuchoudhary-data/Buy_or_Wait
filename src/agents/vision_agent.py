from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from src.agents.cache import read_cache, write_cache
from src.agents.vision_local import extract_local_image
from src.infrastructure.config import get_settings
from src.infrastructure.llm import invoke_vision
from src.infrastructure.logging import get_logger
from src.models.domain import FinancialEvent, ImageRef
from src.models.evidence import ImageExtraction
from src.prompts import vision_prompts

logger = get_logger("vision")


def _data_url(path: str) -> str:
    raw = Path(path).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        cleaned = str(value).replace(",", "").replace(" ", "")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _confidence(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    text = str(value).strip().lower()
    mapping = {"high": 0.9, "medium": 0.6, "low": 0.3, "none": 0.0}
    if text in mapping:
        return mapping[text]
    try:
        return max(0.0, min(1.0, float(text)))
    except ValueError:
        return 0.5


def _date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def extract_image_amount(image: ImageRef, event: Optional[FinancialEvent]) -> ImageExtraction:
    cached = read_cache("vision", image.image_id)
    if cached:
        return ImageExtraction.model_validate(cached)
    local = extract_local_image(image, event)
    if local.amount is not None:
        write_cache("vision", image.image_id, local.model_dump(mode="json"))
        return local
    if not image.path:
        return ImageExtraction(
            image_id=image.image_id,
            related_event_id=image.related_event_id,
            confidence=0.0,
            notes="image file missing",
        )
    if not get_settings().use_llm:
        return local
    event_id = event.event_id if event else image.related_event_id or ""
    description = event.description if event else ""
    category = event.category if event else ""
    currency = event.currency if event else ""
    status = event.status.value if event else ""
    try:
        payload = invoke_vision(
            vision_prompts.SYSTEM_PROMPT,
            vision_prompts.user_prompt(
                image.image_id, event_id, description, category, currency, status
            ),
            _data_url(image.path),
        )
    except Exception as exc:
        logger.warning("vision extraction failed for %s: %s", image.image_id, exc)
        return ImageExtraction(
            image_id=image.image_id,
            related_event_id=image.related_event_id,
            confidence=0.0,
            notes="vision_call_failed",
        )
    extraction = ImageExtraction(
        image_id=image.image_id,
        related_event_id=image.related_event_id,
        amount=_decimal(payload.get("amount")),
        currency=payload.get("currency") or currency or None,
        document_date=_date(payload.get("document_date")),
        amount_role=str(payload.get("amount_role") or ""),
        confidence=_confidence(payload.get("confidence")),
        notes=str(payload.get("notes") or ""),
        raw=payload,
    )
    write_cache("vision", image.image_id, extraction.model_dump(mode="json"))
    return extraction
