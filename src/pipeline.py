from __future__ import annotations

import time
from datetime import datetime, timezone

from src.agents.message_agent import extract_message_facts
from src.agents.vision_agent import extract_image_amount
from src.data.repositories import Repository
from src.domain.decisions.output import write_output
from src.evaluation.usage import build_run_report, write_usage_report
from src.infrastructure.config import get_settings
from src.infrastructure.logging import get_logger
from src.infrastructure.token_tracker import tracker
from src.orchestration.graph import build_graph

logger = get_logger("pipeline")


def prefetch_evidence(repository: Repository, user_ids: set[str] | None = None) -> tuple[dict, dict]:
    image_facts: dict[str, list] = {}
    for image in repository.all_images():
        if user_ids is not None and image.user_id not in user_ids:
            continue
        event = repository.get_event(image.related_event_id) if image.related_event_id else None
        extraction = extract_image_amount(image, event)
        image_facts.setdefault(image.user_id, []).append(extraction)
        logger.info("image %s amount=%s conf=%s", image.image_id, extraction.amount, extraction.confidence)

    message_facts: dict[str, list] = {}
    for message in repository.all_messages():
        if user_ids is not None and message.user_id not in user_ids:
            continue
        facts = extract_message_facts(message)
        message_facts.setdefault(message.user_id, []).extend(facts)
    return image_facts, message_facts


def run(mode: str = "evaluation", use_llm_explanation: bool = False) -> None:
    settings = get_settings()
    tracker.reset()
    repository = Repository()
    graph = build_graph(repository)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = time.perf_counter()

    requests = repository.sample_requests() if mode == "samples" else repository.evaluation_requests()
    image_facts, message_facts = prefetch_evidence(
        repository, {item.user_id for item in requests}
    )
    decisions = []
    for index, request in enumerate(requests, start=1):
        logger.info("processing %s (%s/%s)", request.request_id, index, len(requests))
        result = graph.invoke(
            {
                "request_id": request.request_id,
                "request": request,
                "image_facts": image_facts.get(request.user_id, []),
                "message_facts": message_facts.get(request.user_id, []),
                "use_llm_explanation": use_llm_explanation,
                "errors": [],
                "uncertainties": [],
            }
        )
        decisions.append(result["decision"])

    output_path = settings.output_path
    if mode == "samples":
        output_path = settings.repo_root / "sample_output.csv"
    write_output(output_path, decisions)
    if mode == "evaluation":
        write_output(settings.dataset_dir / "output.csv", decisions)
    run_report = build_run_report(
        mode=mode,
        started_at=started_at,
        elapsed_seconds=time.perf_counter() - started,
        requests=requests,
        decisions=decisions,
        image_facts=image_facts,
        message_facts=message_facts,
        repository=repository,
        output_path=output_path,
    )
    write_usage_report(len(decisions), run_report)
    logger.info("wrote %s rows to %s", len(decisions), output_path)
