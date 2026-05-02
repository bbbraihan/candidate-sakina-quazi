"""
Retrieval recall evaluation — Recall@k and per-strategy comparisons.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger


def recall_at_k(expected_ids: list[str], returned_ids: list[str], k: int) -> float:
    """Return the fraction of expected IDs found in the first k returned IDs."""
    if not expected_ids:
        return 0.0
    top_k = set(returned_ids[:k])
    hits = sum(1 for eid in expected_ids if eid in top_k)
    return hits / len(expected_ids)


def eval_recall() -> dict[str, Any]:
    """Evaluate retrieval quality (Recall@3 and Recall@5) against ground-truth labels.

    Uses search_hybrid directly — no LLM call needed, retrieval is model-independent.
    """
    from sakina.search import search_hybrid as _search_hybrid

    with open("dataset/labels.json", "r", encoding="utf-8") as hndl:
        labels = json.load(hndl)
        queries = labels["queries"]

    recalls_at_3 = []
    recalls_at_5 = []
    per_query = []

    for entry in queries:
        query = entry["query"]
        expected_ids = entry["expected_ids"]

        logger.info(f"Evaluating query {entry['query_id']}: {query}...")

        passages = _search_hybrid(query, n_results=10)
        seen: set[str] = set()
        retrieved_document_ids: list[str] = []
        for p in passages:
            doc_id = str(p.get("id", ""))
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                retrieved_document_ids.append(doc_id)

        r3 = recall_at_k(expected_ids, retrieved_document_ids, 3)
        r5 = recall_at_k(expected_ids, retrieved_document_ids, 5)

        recalls_at_3.append(r3)
        recalls_at_5.append(r5)

        per_query.append({
            "query_id": entry["query_id"],
            "query": query,
            "expected_ids": expected_ids,
            "retrieved_ids": retrieved_document_ids,
            "recall_at_3": r3,
            "recall_at_5": r5,
        })

    avg_r3 = sum(recalls_at_3) / len(recalls_at_3) if recalls_at_3 else 0.0
    avg_r5 = sum(recalls_at_5) / len(recalls_at_5) if recalls_at_5 else 0.0

    print(f"\nAverage Recall@3: {avg_r3:.2f}")
    print(f"Average Recall@5: {avg_r5:.2f}")

    return {"avg_r3": avg_r3, "avg_r5": avg_r5, "per_query": per_query}


def eval_retrieval_strategies() -> dict[str, Any]:
    """Compare Recall@5 for semantic-only, BM25-only, and hybrid RRF retrieval."""
    from sakina.search import search_embeddings, search_bm25, search_hybrid

    with open("dataset/labels.json", "r", encoding="utf-8") as f:
        labels = json.load(f)
    queries = labels["queries"]

    strategy_fns = {
        "semantic": search_embeddings,
        "bm25": search_bm25,
        "hybrid": search_hybrid,
    }

    per_query: list[dict[str, Any]] = []
    buckets: dict[str, list[float]] = {s: [] for s in strategy_fns}

    print("\n=== Retrieval Strategy Comparison ===\n")
    print(f"{'Query ID':<10} {'semantic':>9} {'bm25':>9} {'hybrid':>9}")
    print("-" * 42)

    for entry in queries:
        qid = entry["query_id"]
        query = entry["query"]
        expected_ids = entry["expected_ids"]
        row: dict[str, Any] = {"query_id": qid, "query": query}
        for name, fn in strategy_fns.items():
            passages = fn(query, n_results=5)
            returned_ids = [p.get("id", "") for p in passages]
            r5 = recall_at_k(expected_ids, returned_ids, 5)
            buckets[name].append(r5)
            row[name] = r5
        per_query.append(row)
        print(f"{qid:<10} {row['semantic']:>9.2f} {row['bm25']:>9.2f} {row['hybrid']:>9.2f}")

    summary = {
        name: round(sum(scores) / len(scores), 4) if scores else 0.0
        for name, scores in buckets.items()
    }
    print("-" * 42)
    print(f"{'Average':<10} {summary['semantic']:>9.2f} {summary['bm25']:>9.2f} {summary['hybrid']:>9.2f}")

    return {"per_query": per_query, "avg_r5": summary}
