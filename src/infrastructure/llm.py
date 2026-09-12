from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from src.infrastructure.config import get_settings
from src.infrastructure.logging import get_logger
from src.infrastructure.token_tracker import tracker

logger = get_logger("llm")

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _chat_model(model: str, temperature: float = 0.0) -> ChatOpenAI:
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not set")
    return ChatOpenAI(
        model=model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
        default_headers={
            "HTTP-Referer": "https://hackerrank.com/orchestrate",
            "X-Title": "Buy or Wait Agent",
        },
    )


def _usage_from_response(response: Any) -> tuple[int, int]:
    metadata = getattr(response, "response_metadata", {}) or {}
    token_usage = metadata.get("token_usage") or metadata.get("usage") or {}
    input_tokens = int(token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0)
    output_tokens = int(
        token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0
    )
    if input_tokens or output_tokens:
        return input_tokens, output_tokens
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return int(getattr(usage, "input_tokens", 0) or 0), int(
            getattr(usage, "output_tokens", 0) or 0
        )
    return 0, 0


def parse_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(raw)
    if not match:
        raise ValueError("Model did not return a JSON object")
    value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Model JSON was not an object")
    return value


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1.5, max=20),
    reraise=True,
)
def invoke_text(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    settings = get_settings()
    model = _chat_model(settings.text_model)
    response = model.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    )
    input_tokens, output_tokens = _usage_from_response(response)
    tracker.record(settings.text_model, input_tokens, output_tokens)
    return parse_json_object(str(response.content))


def _invoke_vision_model(
    model_name: str, system_prompt: str, user_prompt: str, image_data_url: str
) -> dict[str, Any]:
    model = _chat_model(model_name)
    response = model.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=[
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ]
            ),
        ]
    )
    input_tokens, output_tokens = _usage_from_response(response)
    tracker.record(model_name, input_tokens, output_tokens)
    return parse_json_object(str(response.content))


_VISION_UNSUPPORTED: set[str] = set()


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1.5, max=20),
    reraise=True,
)
def invoke_vision(system_prompt: str, user_prompt: str, image_data_url: str) -> dict[str, Any]:
    settings = get_settings()
    models = [settings.image_model]
    if settings.vision_fallback_model and settings.vision_fallback_model not in models:
        models.append(settings.vision_fallback_model)
    last_error: Exception | None = None
    for model_name in models:
        if not model_name or model_name in _VISION_UNSUPPORTED:
            continue
        try:
            return _invoke_vision_model(model_name, system_prompt, user_prompt, image_data_url)
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            if "image" in message or "vision" in message or "404" in message:
                _VISION_UNSUPPORTED.add(model_name)
                logger.warning("vision model %s unsupported or failed; trying fallback", model_name)
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("No vision model configured")
