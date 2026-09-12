from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from src.agents.cache import read_cache, write_cache
from src.agents.message_rules import parse_message
from src.infrastructure.config import get_settings
from src.infrastructure.llm import invoke_text
from src.infrastructure.logging import get_logger
from src.models.domain import Message
from src.models.evidence import MessageExtraction
from src.prompts import message_prompts

logger = get_logger("messages")


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
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


def extract_message_facts(message: Message) -> list[MessageExtraction]:
    cached = read_cache("messages", message.message_id)
    if cached:
        return [MessageExtraction.model_validate(item) for item in cached.get("facts", [])]
    ruled = parse_message(message)
    if ruled:
        write_cache(
            "messages",
            message.message_id,
            {"facts": [fact.model_dump(mode="json") for fact in ruled], "source": "rules"},
        )
        return ruled
    if not get_settings().use_llm:
        return []
    try:
        payload = invoke_text(
            message_prompts.SYSTEM_PROMPT,
            message_prompts.user_prompt(
                message.message_id,
                message.source_type,
                message.sent_at.isoformat(),
                message.message_text,
                message.related_event_id,
            ),
        )
    except Exception as exc:
        logger.warning("message extraction failed for %s: %s", message.message_id, exc)
        return []
    facts: list[MessageExtraction] = []
    for item in payload.get("facts", []) if isinstance(payload.get("facts"), list) else []:
        facts.append(
            MessageExtraction(
                message_id=message.message_id,
                fact_type=str(item.get("fact_type") or "other"),
                related_event_id=item.get("related_event_id") or message.related_event_id,
                amount=_decimal(item.get("amount")),
                secondary_amount=_decimal(item.get("secondary_amount")),
                currency=item.get("currency"),
                effective_date=_date(item.get("effective_date")),
                applies_once=bool(item.get("applies_once")),
                confirmed=bool(item.get("confirmed")),
                description=str(item.get("description") or ""),
                confidence=_confidence(item.get("confidence")),
                ignore_as_income=bool(item.get("ignore_as_income")),
            )
        )
    write_cache(
        "messages",
        message.message_id,
        {"facts": [fact.model_dump(mode="json") for fact in facts]},
    )
    return facts
