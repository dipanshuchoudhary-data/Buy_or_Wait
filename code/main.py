from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Buy or Wait batch runner")
    parser.add_argument(
        "--mode",
        choices=("evaluation", "samples"),
        default="evaluation",
        help="evaluation writes output.csv for requests.csv; samples scores public examples",
    )
    parser.add_argument(
        "--llm-explanations",
        action="store_true",
        help="use the text model for explanations instead of the deterministic template",
    )
    args = parser.parse_args()
    run(mode=args.mode, use_llm_explanation=args.llm_explanations)


if __name__ == "__main__":
    main()
