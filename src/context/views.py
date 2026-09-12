from __future__ import annotations

from src.models.domain import FinancialEvent, ImageRef, Message, Request, UserProfile
from src.models.output import CandidatePlan


def vision_context(image: ImageRef, event: FinancialEvent | None) -> dict:
    return {
        "image_id": image.image_id,
        "event_id": event.event_id if event else image.related_event_id,
        "description": event.description if event else "",
        "category": event.category if event else "",
        "currency": event.currency if event else "",
    }


def message_context(message: Message) -> dict:
    return {
        "message_id": message.message_id,
        "source_type": message.source_type,
        "related_event_id": message.related_event_id,
        "text": message.message_text,
    }


def explanation_context(
    request: Request,
    profile: UserProfile,
    plan: CandidatePlan | None,
) -> dict:
    return {
        "request_id": request.request_id,
        "currency": profile.home_currency,
        "minimum_balance": str(profile.minimum_balance_to_keep),
        "requested_amount": str(request.requested_amount),
        "method": plan.method.value if plan else "not_recommended",
    }
