from __future__ import annotations

import csv
from pathlib import Path

from src.evaluation.metrics import amounts_close
from src.infrastructure.config import get_settings


COMPARE_FIELDS = [
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
]


def _read(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return {row["request_id"]: row for row in csv.DictReader(handle)}


def evaluate_samples(predicted_path: Path | None = None) -> dict:
    settings = get_settings()
    actual = _read(settings.dataset_dir / "sample_requests.csv")
    predicted_path = predicted_path or settings.repo_root / "sample_output.csv"
    predicted = _read(predicted_path)
    rows = []
    matches = {field: 0 for field in COMPARE_FIELDS}
    status_method = 0
    for request_id, truth in actual.items():
        pred = predicted.get(request_id, {})
        row = {"request_id": request_id}
        all_ok = True
        for field in COMPARE_FIELDS:
            expected = (truth.get(field) or "").strip()
            got = (pred.get(field) or "").strip()
            if field == "amount_safe_to_pay":
                ok = amounts_close(expected or "0", got or "0")
            else:
                ok = expected == got
            row[field] = "ok" if ok else f"{got!r} != {expected!r}"
            if ok:
                matches[field] += 1
            else:
                all_ok = False
        if (
            (truth.get("affordability_status") or "") == (pred.get("affordability_status") or "")
            and (truth.get("recommended_payment_method") or "")
            == (pred.get("recommended_payment_method") or "")
        ):
            status_method += 1
        row["all"] = all_ok
        rows.append(row)
    total = len(actual)
    return {
        "total": total,
        "per_field": {field: f"{matches[field]}/{total}" for field in COMPARE_FIELDS},
        "status_and_method": f"{status_method}/{total}",
        "rows": rows,
    }


def main() -> None:
    report = evaluate_samples()
    print("status+method", report["status_and_method"])
    print(report["per_field"])
    for row in report["rows"]:
        if not row["all"]:
            print(row)


if __name__ == "__main__":
    main()
