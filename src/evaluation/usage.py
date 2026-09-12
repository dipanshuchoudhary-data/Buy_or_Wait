from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.infrastructure.config import get_settings
from src.infrastructure.token_tracker import ModelUsage, tracker


def _rate(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * _rate("LLM_USD_PER_MILLION_INPUT", 0.0)
        + output_tokens / 1_000_000 * _rate("LLM_USD_PER_MILLION_OUTPUT", 0.0)
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RunReport:
    mode: str = "evaluation"
    request_count: int = 0
    started_at: str = ""
    finished_at: str = ""
    elapsed_seconds: float = 0.0
    unique_users: int = 0
    images_processed: int = 0
    messages_processed: int = 0
    profiles: int = 0
    events: int = 0
    payment_option_rows: int = 0
    fx_rows: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    method_counts: dict[str, int] = field(default_factory=dict)
    explanations_written: int = 0
    output_path: str = "output.csv"
    vision_cache_files: int = 0
    message_cache_files: int = 0


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def _table(rows: list[tuple[str, str]]) -> list[str]:
    lines = []
    for label, value in rows:
        lines.append(f"- {label}: {value}")
    return lines


def render_usage_report(request_count: int, run: RunReport | None = None) -> str:
    settings = get_settings()
    totals = tracker.totals()
    run = run or RunReport(request_count=request_count, finished_at=_utc_now())
    if not run.request_count:
        run.request_count = request_count

    throughput = (
        run.request_count / run.elapsed_seconds if run.elapsed_seconds > 0 else 0.0
    )
    output_name = Path(run.output_path).name if run.output_path else "output.csv"

    status_lines = [
        f"| `{name}` | {count} | {count / run.request_count * 100:.1f}% |"
        for name, count in sorted(run.status_counts.items())
    ] or ["| _(none)_ | 0 | 0.0% |"]
    method_lines = [
        f"| `{name}` | {count} | {count / run.request_count * 100:.1f}% |"
        for name, count in sorted(run.method_counts.items())
    ] or ["| _(none)_ | 0 | 0.0% |"]

    lines = [
        "# Full-dataset run report",
        "",
        "This file records the final run that produced `output.csv`.",
        "",
        "## Run",
        "",
        *_table(
            [
                ("Mode", run.mode),
                ("Output file", output_name),
                ("Requests written", str(run.request_count)),
                ("Unique users", str(run.unique_users)),
                ("Started (UTC)", run.started_at or "—"),
                ("Finished (UTC)", run.finished_at or _utc_now()),
                ("Wall time (seconds)", f"{run.elapsed_seconds:.2f}"),
                ("Throughput (requests/second)", f"{throughput:.3f}"),
                ("Forecast horizon (days)", str(settings.forecast_days)),
                ("Decision engine", "deterministic financial graph with local evidence extractors"),
            ]
        ),
        "",
        "## Ledger and evidence coverage",
        "",
        *_table(
            [
                ("Financial profiles", str(run.profiles)),
                ("Financial events", str(run.events)),
                ("Payment-option rows", str(run.payment_option_rows)),
                ("Exchange-rate rows", str(run.fx_rows)),
                ("Images resolved", str(run.images_processed)),
                ("Messages parsed", str(run.messages_processed)),
                ("Vision cache files", str(run.vision_cache_files)),
                ("Message cache files", str(run.message_cache_files)),
                ("Non-empty explanations", str(run.explanations_written)),
            ]
        ),
        "",
        "## Decision mix",
        "",
        "### Affordability status",
        "",
        "| Status | Count | Share |",
        "|---|---:|---:|",
        *status_lines,
        "",
        "### Recommended payment method",
        "",
        "| Method | Count | Share |",
        "|---|---:|---:|",
        *method_lines,
        "",
        "## Notes",
        "",
        "- API keys, credentials, and environment secrets are not included.",
        "- Every plan is checked against the 90-day cash forecast and the minimum-balance constraint before a row is written.",
        "",
    ]

    total_cost = _cost(totals.input_tokens, totals.output_tokens)
    avg_tokens = totals.total_tokens / run.request_count if run.request_count else 0.0
    avg_cost = total_cost / run.request_count if run.request_count else 0.0
    avg_input = totals.input_tokens / run.request_count if run.request_count else 0.0
    avg_output = totals.output_tokens / run.request_count if run.request_count else 0.0
    usages: list[ModelUsage] = [item for item in tracker.usages.values() if item.calls > 0]
    if not usages:
        usages = [ModelUsage(provider="local", model="local-rules+catalog")]
    provider = "OpenRouter" if totals.calls > 0 else "none (local rules + image catalog)"
    text_model = settings.text_model if totals.calls > 0 and settings.text_model else "none"
    vision_model = settings.image_model if totals.calls > 0 and settings.image_model else "none"
    model_rows = [
        f"| `{usage.model}` | {usage.calls} | {usage.input_tokens} | {usage.output_tokens} | "
        f"{usage.total_tokens} | {_cost(usage.input_tokens, usage.output_tokens):.6f} |"
        for usage in usages
    ]
    lines.extend(
        [
            "## Provider usage",
            "",
            *_table(
                [
                    ("Provider", provider),
                    ("Text model", f"`{text_model}`"),
                    ("Vision model", f"`{vision_model}`"),
                ]
            ),
            "",
            "| Model | Calls | Input tokens | Output tokens | Total tokens | Estimated cost (USD) |",
            "|---|---:|---:|---:|---:|---:|",
            *model_rows,
            f"| **All** | **{totals.calls}** | **{totals.input_tokens}** | **{totals.output_tokens}** | "
            f"**{totals.total_tokens}** | **{total_cost:.6f}** |",
            "",
            *_table(
                [
                    ("Requests processed", str(run.request_count)),
                    ("Average input tokens per request", f"{avg_input:.2f}"),
                    ("Average output tokens per request", f"{avg_output:.2f}"),
                    ("Average total tokens per request", f"{avg_tokens:.2f}"),
                    ("Estimated average cost per request (USD)", f"{avg_cost:.6f}"),
                    ("Estimated total cost (USD)", f"{total_cost:.6f}"),
                ]
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_usage_report(request_count: int, run: RunReport | None = None) -> None:
    text = render_usage_report(request_count, run)
    targets = [
        get_settings().evaluation_dir / "usage_report.md",
        get_settings().repo_root / "code" / "evaluation" / "usage_report.md",
        get_settings().repo_root / "src" / "evaluation" / "usage_report.md",
    ]
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def build_run_report(
    *,
    mode: str,
    started_at: str,
    elapsed_seconds: float,
    requests: list,
    decisions: list,
    image_facts: dict,
    message_facts: dict,
    repository,
    output_path: Path,
) -> RunReport:
    settings = get_settings()
    dataset = repository.dataset
    user_ids = {item.user_id for item in requests}
    status_counts = Counter(item.affordability_status.value for item in decisions)
    method_counts = Counter(item.recommended_payment_method.value for item in decisions)
    return RunReport(
        mode=mode,
        request_count=len(decisions),
        started_at=started_at,
        finished_at=_utc_now(),
        elapsed_seconds=elapsed_seconds,
        unique_users=len(user_ids),
        images_processed=sum(1 for image in repository.all_images() if image.user_id in user_ids),
        messages_processed=sum(
            1 for message in repository.all_messages() if message.user_id in user_ids
        ),
        profiles=len(dataset.profiles),
        events=sum(len(items) for items in dataset.events.values()),
        payment_option_rows=sum(len(items) for items in dataset.payment_options.values()),
        fx_rows=len(dataset.rates),
        status_counts=dict(status_counts),
        method_counts=dict(method_counts),
        explanations_written=sum(1 for item in decisions if (item.decision_explanation or "").strip()),
        output_path=str(output_path),
        vision_cache_files=_count_files(settings.cache_dir / "vision"),
        message_cache_files=_count_files(settings.cache_dir / "messages"),
    )
