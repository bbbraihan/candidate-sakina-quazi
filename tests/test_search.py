from unittest.mock import patch
from sakina.search import search_hybrid


def _make_result(doc_id: str, score: float = 0.9) -> dict:
    return {"id": doc_id, "document": f"text for {doc_id}", "similarity": score}


def test_hybrid_rrf_merges_both_sources():
    sem = [_make_result("a"), _make_result("b")]
    bm25 = [_make_result("b"), _make_result("c")]

    with patch("sakina.search.search_embeddings", return_value=sem), \
         patch("sakina.search.search_bm25", return_value=bm25):
        results = search_hybrid("query", n_results=10)

    ids = [r["id"] for r in results]
    assert set(ids) == {"a", "b", "c"}


def test_hybrid_rrf_ranks_shared_doc_higher():
    # "b" appears in both lists so its RRF score should beat "a" and "c"
    sem = [_make_result("a"), _make_result("b")]
    bm25 = [_make_result("b"), _make_result("c")]

    with patch("sakina.search.search_embeddings", return_value=sem), \
         patch("sakina.search.search_bm25", return_value=bm25):
        results = search_hybrid("query", n_results=10)

    assert results[0]["id"] == "b"


def test_hybrid_respects_n_results():
    sem = [_make_result(f"s{i}") for i in range(10)]
    bm25 = [_make_result(f"b{i}") for i in range(10)]

    with patch("sakina.search.search_embeddings", return_value=sem), \
         patch("sakina.search.search_bm25", return_value=bm25):
        results = search_hybrid("query", n_results=5)

    assert len(results) == 5


def test_hybrid_sem_only():
    sem = [_make_result("a"), _make_result("b")]

    with patch("sakina.search.search_embeddings", return_value=sem), \
         patch("sakina.search.search_bm25", return_value=[]):
        results = search_hybrid("query", n_results=10)

    assert [r["id"] for r in results] == ["a", "b"]


def test_hybrid_empty_results():
    with patch("sakina.search.search_embeddings", return_value=[]), \
         patch("sakina.search.search_bm25", return_value=[]):
        results = search_hybrid("query", n_results=10)

    assert results == []
