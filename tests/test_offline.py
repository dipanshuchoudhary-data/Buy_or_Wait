from datetime import date
from decimal import Decimal
from unittest.mock import patch

from src.agents.message_agent import extract_message_facts
from src.agents.message_rules import parse_message
from src.agents.vision_agent import extract_image_amount
from src.agents.vision_local import extract_local_image
from src.models.domain import ImageRef, Message
from datetime import datetime, timezone


def test_message_extraction_does_not_call_llm() -> None:
    message = Message(
        message_id="message_offline",
        user_id="user_x",
        sent_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_type="employer",
        message_text="Your temporary monthly pay is EUR 1037.52.",
    )
    with patch("src.agents.message_agent.invoke_text") as mocked:
        facts = extract_message_facts(message)
        mocked.assert_not_called()
    assert facts[0].amount == Decimal("1037.52")


def test_unknown_message_stays_offline() -> None:
    message = Message(
        message_id="message_offline_unknown",
        user_id="user_x",
        sent_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_type="bank",
        message_text="Hello, this is a generic note with no financial change.",
    )
    assert parse_message(message) == []
    with patch("src.agents.message_agent.invoke_text") as mocked:
        facts = extract_message_facts(message)
        mocked.assert_not_called()
    assert facts == []


def test_local_vision_reads_payslip_without_api() -> None:
    image = ImageRef(image_id="image_01", user_id="user_03", related_event_id="event_253")
    extraction = extract_local_image(image)
    assert extraction.amount == Decimal("4365000")
    with patch("src.agents.vision_agent.invoke_vision") as mocked:
        result = extract_image_amount(image, None)
        mocked.assert_not_called()
    assert result.amount == Decimal("4365000")
