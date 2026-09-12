from __future__ import annotations

from src.infrastructure.llm import invoke_text
from src.infrastructure.logging import get_logger
from src.models.evidence import ConflictRecord
from src.prompts import reconciliation_prompts

logger = get_logger("reconcile")


def resolve_conflict(topic: str, structured: str, evidence: str) -> ConflictRecord:
    try:
        payload = invoke_text(
            reconciliation_prompts.SYSTEM_PROMPT,
            reconciliation_prompts.user_prompt(topic, structured, evidence),
        )
        return ConflictRecord(
            topic=topic,
            resolution=str(payload.get("resolution") or "safer_interpretation"),
            safer_choice=str(payload.get("safer_choice") or "ignore_unconfirmed"),
            sources=["structured", "evidence"],
            auto_resolved=True,
        )
    except Exception as exc:
        logger.warning("reconciliation failed for %s: %s", topic, exc)
        return ConflictRecord(
            topic=topic,
            resolution="model_failed_safer_default",
            safer_choice="ignore_unconfirmed_or_keep_existing_settled",
            sources=["structured", "evidence"],
            auto_resolved=True,
        )
