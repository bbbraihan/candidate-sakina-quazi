"""
Sakina Health evaluation suite — retrieval recall, citation faithfulness,
adversarial safety scoring, latency benchmarking, and Markdown report generation.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from sakina import config
from sakina.eval.recall import recall_at_k, eval_recall, eval_retrieval_strategies
from sakina.eval.safety import evaluate_with_llm
from sakina.eval.faithfulness import eval_faithfulness
from sakina.eval.latency import eval_latency
from sakina.eval.report import generate_eval_md, generate_latency_md, generate_comparison_md

__all__ = [
    "recall_at_k",
    "eval_recall",
    "eval_retrieval_strategies",
    "evaluate_with_llm",
    "eval_faithfulness",
    "eval_latency",
    "generate_eval_md",
    "generate_latency_md",
    "generate_comparison_md",
    "eval_all_models",
]


@contextmanager
def _use_model(model: str) -> Generator[None, None, None]:
    """Context manager that temporarily overrides config.CHAT_MODEL for a single eval run."""
    original = config.CHAT_MODEL
    config.CHAT_MODEL = model
    try:
        yield
    finally:
        config.CHAT_MODEL = original


def eval_all_models(tasks: tuple[str, ...] = ("recall", "safety", "faithfulness")) -> dict[str, dict[str, Any]]:
    """Run eval tasks for every model in config.CHAT_MODELS and return results keyed by model.

    Recall is model-independent (embedding-only), so it runs once and is shared across all models.
    """
    shared_recall = None
    if "recall" in tasks:
        print("\n=== Retrieval Recall (shared across all models) ===")
        shared_recall = eval_recall()

    all_results = {}
    for model in config.CHAT_MODELS:
        print(f"\n{'='*60}")
        print(f"Evaluating model: {model}")
        print(f"{'='*60}")
        with _use_model(model):
            model_results = {}
            if shared_recall is not None:
                model_results["recall"] = shared_recall
            if "safety" in tasks:
                model_results["safety"] = evaluate_with_llm(judge_model=config.JUDGE_MODEL)
            if "faithfulness" in tasks:
                model_results["faithfulness"] = eval_faithfulness()
        all_results[model] = model_results
    return all_results
