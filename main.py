from __future__ import annotations

import argparse

from src.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Buy or Wait batch runner")
    parser.add_argument("--mode", choices=("evaluation", "samples"), default="evaluation")
    parser.add_argument("--llm-explanations", action="store_true")
    args = parser.parse_args()
    run(mode=args.mode, use_llm_explanation=args.llm_explanations)


if __name__ == "__main__":
    main()
