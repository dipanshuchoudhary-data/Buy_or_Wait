from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EvidenceSource(str, Enum):
    PROFILE = "profile"
    EVENT = "event"
    MESSAGE = "message"
    IMAGE = "image"
    PAYMENT_OPTION = "payment_option"
    EXCHANGE_RATE = "exchange_rate"
    MODEL = "model"


class Evidence(BaseModel):
    source: EvidenceSource
    source_id: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class FinancialFact(BaseModel):
    fact_type: str
    event_id: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    effective_date: Optional[date] = None
    description: str = ""
    confidence: float = 1.0
    evidence_ids: list[str] = Field(default_factory=list)
    trusted: bool = False


class ImageExtraction(BaseModel):
    image_id: str
    related_event_id: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    document_date: Optional[date] = None
    amount_role: str = ""
    confidence: float = 0.0
    notes: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class MessageExtraction(BaseModel):
    message_id: str
    fact_type: str
    related_event_id: Optional[str] = None
    amount: Optional[Decimal] = None
    secondary_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    effective_date: Optional[date] = None
    applies_once: bool = False
    confirmed: bool = False
    description: str = ""
    confidence: float = 0.0
    ignore_as_income: bool = False


class ConflictRecord(BaseModel):
    topic: str
    event_id: Optional[str] = None
    resolution: str
    safer_choice: str
    sources: list[str] = Field(default_factory=list)
    auto_resolved: bool = True
