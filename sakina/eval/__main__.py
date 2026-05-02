"""
CLI entry point: python -m sakina.eval [--default-model | --all-models | --latency]
"""

from __future__ import annotations

import argparse
import sys

from sakina.eval import (
    eval_recall,
    eval_retrieval_strategies,
    evaluate_with_llm,
    eval_faithfulness,
    eval_latency,
    eval_all_models,
    generate_eval_md,
    generate_latency_md,
    generate_comparison_md,
)


class _Tee:
    """Write to both stdout and a file simultaneously."""

    def __init__(self, path: str) -> None:
        self._file = open(path, "w", encoding="utf-8")
        self._stdout = sys.stdout
        sys.stdout = self

    def write(self, data: str) -> int:
        self._file.write(data)
        return self._stdout.write(data)

    def flush(self) -> None:
        self._file.flush()
        self._stdout.flush()

    def close(self) -> None:
        sys.stdout = self._stdout
        self._file.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sakina Health evaluation suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m sakina.eval --default-model  # recall + safety + faithfulness for default model → reports/EVAL_REPORT.md\n"
            "  python -m sakina.eval --all-models     # same tasks across all models in config.CHAT_MODELS → reports/EVAL_COMPARISON.md\n"
            "  python -m sakina.eval --latency        # latency benchmarks for default model → reports/latency.md\n"
        ),
    )
    parser.add_argument(
        "--default-model",
        action="store_true",
        help="Run recall, safety, and faithfulness for the default model (config.CHAT_MODEL)",
    )
    parser.add_argument(
        "--all-models",
        action="store_true",
        help="Run recall, safety, and faithfulness across every model in config.CHAT_MODELS",
    )
    parser.add_argument(
        "--latency",
        action="store_true",
        help="Run latency benchmarks for the default model and write reports/latency.md",
    )
    args = parser.parse_args()

    if args.default_model:
        log_path = "reports/EVAL_REPORT_LOG.md"
        tee = _Tee(log_path)
        try:
            recall_res = eval_recall()
            strategies_res = eval_retrieval_strategies()
            safety_res = evaluate_with_llm()
            faith_res = eval_faithfulness()
            md = generate_eval_md(recall_res, safety_res, faith_res, strategies=strategies_res)
            with open("reports/EVAL_REPORT.md", "w", encoding="utf-8") as f:
                f.write(md)
            print("\nreports/EVAL_REPORT.md written.")
        finally:
            tee.close()
            print(f"{log_path} written.", flush=True)
    elif args.all_models:
        log_path = "reports/EVAL_COMPARISON_LOG.md"
        tee = _Tee(log_path)
        try:
            all_results = eval_all_models()
            strategies_res = eval_retrieval_strategies()
            md = generate_comparison_md(all_results, strategies=strategies_res)
            with open("reports/EVAL_COMPARISON.md", "w", encoding="utf-8") as f:
                f.write(md)
            print("\nreports/EVAL_COMPARISON.md written.")
        finally:
            tee.close()
            print(f"{log_path} written.", flush=True)
    elif args.latency:
        log_path = "reports/latency_log.md"
        tee = _Tee(log_path)
        try:
            latency_res = eval_latency()
            md = generate_latency_md(latency_res)
            with open("reports/latency.md", "w", encoding="utf-8") as f:
                f.write(md)
            print("\nreports/latency.md written.")
        finally:
            tee.close()
            print(f"{log_path} written.", flush=True)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
