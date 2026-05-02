"""
Citation faithfulness evaluation — checks that LLM-reported citations come from retrieved docs.
"""

from __future__ import annotations

import json
import os
from typing import Any

from sakina.chat import generate_response


def eval_faithfulness(dataset_path: str = "dataset/labels.json") -> dict[str, Any]:
    """
    Citation faithfulness: fraction of model-reported citation IDs that
    actually appear in the retrieved set. Score = 1.0 means no hallucination.

    Rubric:
      1.0  Model cited only IDs present in the retrieved set
      0.5  Half of self-reported citations were hallucinated IDs
      0.0  All self-reported citations were fabricated
      N/A  Model returned no citations (out-of-scope reply) — scores 1.0
    """
    with open(dataset_path, "r", encoding="utf-8") as f:
        labels = json.load(f)
    queries = labels["queries"]

    manual = {}
    manual_path = "dataset/faithfulness_manual.jsonl"
    if os.path.exists(manual_path):
        with open(manual_path, "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                manual[row["query_id"]] = row

    print("\n=== Faithfulness Evaluation ===\n")
    header = f"{'ID':<6} {'Score':>6}  {'Raw':>4}  {'Filtered':>8}  {'Hallucinated IDs'}"
    if manual:
        header += f"  {'Manual':>6}"
    print(header)
    print("-" * (len(header) + 10))

    scores = []
    results = []

    for entry in queries:
        qid = entry["query_id"]
        query = entry["query"]

        response, citations, retrieved_ids, raw_citations = generate_response(query)

        if not raw_citations:
            score = 1.0
            hallucinated = []
        else:
            hallucinated = [cid for cid in raw_citations if cid not in retrieved_ids]
            score = len(citations) / len(raw_citations)

        scores.append(score)
        results.append({
            "query_id": qid,
            "query": query,
            "response": response,
            "score": score,
            "raw_citations": raw_citations,
            "filtered_citations": citations,
            "hallucinated": hallucinated,
        })

        row = (
            f"{qid:<6} {score:>6.2f}  {len(raw_citations):>4}  {len(citations):>8}"
            f"  {', '.join(hallucinated) if hallucinated else '—'}"
        )
        if manual and qid in manual:
            row += f"  {manual[qid]['expected_faithfulness']:>6.2f}"
        print(row)

    avg = sum(scores) / len(scores) if scores else 0.0
    print(f"\nAverage Faithfulness Score: {avg:.2f}")

    if manual:
        common = [r for r in results if r["query_id"] in manual]
        if common:
            llm_scores = [r["score"] for r in common]
            man_scores = [manual[r["query_id"]]["expected_faithfulness"] for r in common]
            mean_diff = sum(abs(a - b) for a, b in zip(llm_scores, man_scores)) / len(common)
            print(f"Mean absolute error vs manual labels: {mean_diff:.2f}")

    return {"average_score": avg, "results": results}
