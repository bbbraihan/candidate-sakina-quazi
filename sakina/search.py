"""
Sakina Health search module — semantic (ChromaDB), BM25, and hybrid retrieval.
"""

from __future__ import annotations

import re
import time
import chromadb
from loguru import logger
from rank_bm25 import BM25Okapi

from . import config
from .embedding import BGEEmbeddingFunction

_embed_fn: BGEEmbeddingFunction | None = None
_client: chromadb.ClientAPI | None = None

_bm25_index: BM25Okapi | None = None
_bm25_docs: list[str] = []
_bm25_metas: list[dict[str, str]] = []
_bm25_ids: list[str] = []


def _get_embed_fn() -> BGEEmbeddingFunction:
    """Return the singleton BGE embedding function, initializing it on first call."""
    global _embed_fn
    if _embed_fn is None:
        _embed_fn = BGEEmbeddingFunction(config.EMBED_MODEL)
    return _embed_fn


def _get_client() -> chromadb.ClientAPI:
    """Return the singleton ChromaDB persistent client, initializing it on first call."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    return _client


def _get_collection() -> chromadb.Collection:
    """Return the 'sakina_content' ChromaDB collection."""
    return _get_client().get_collection("sakina_content", embedding_function=_get_embed_fn())


def _build_bm25_index() -> None:
    """Load all documents from ChromaDB and build an in-memory BM25 index."""
    global _bm25_index, _bm25_docs, _bm25_metas, _bm25_ids
    t0 = time.perf_counter()
    all_data = _get_collection().get(include=["documents", "metadatas"])
    _bm25_docs = all_data["documents"]
    _bm25_metas = all_data["metadatas"]
    _bm25_ids = all_data["ids"]
    tokenized = [re.findall(r'\w+', doc.lower()) for doc in _bm25_docs]
    _bm25_index = BM25Okapi(tokenized)
    logger.info(f"BM25 index built: {len(_bm25_docs)} docs in {(time.perf_counter()-t0)*1000:.0f}ms")


def search_embeddings(query: str, n_results: int = 5) -> list[dict]:
    """Retrieve the top-n passages most semantically similar to the query using ChromaDB."""
    t0 = time.perf_counter()
    try:
        query_prefix = "Represent this sentence for searching relevant passages"
        search_results = _get_collection().query(
            query_texts=[f"{query_prefix}: {query}"],
            n_results=n_results,
        )

        documents = search_results['documents'][0] if search_results['documents'] else []
        metadatas = search_results['metadatas'][0] if search_results['metadatas'] else []
        distances = search_results['distances'][0] if search_results['distances'] else []

        results = []
        for metadata, document, distance in zip(metadatas, documents, distances):
            result = {'document': document}
            result.update(metadata)
            result['similarity'] = 1 - distance
            results.append(result)

        logger.info(f"semantic search: {len(results)} results in {(time.perf_counter()-t0)*1000:.0f}ms")
        if not results:
            logger.warning("semantic search returned 0 results")
        return results
    except Exception as e:
        logger.error(f"semantic search failed after {(time.perf_counter()-t0)*1000:.0f}ms: {e}")
        return []


def search_bm25(query: str, n_results: int = 5) -> list[dict]:
    """Retrieve the top-n passages by BM25 keyword score, building the index on first call."""
    if _bm25_index is None:
        _build_bm25_index()
    t0 = time.perf_counter()
    tokens = re.findall(r'\w+', query.lower())
    scores = _bm25_index.get_scores(tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_results]
    results = []
    for idx in top_indices:
        meta = dict(_bm25_metas[idx])
        results.append({
            'document': _bm25_docs[idx],
            'id': _bm25_ids[idx],
            **meta,
            'bm25_score': float(scores[idx]),
        })
    logger.info(f"BM25 search: {len(results)} results in {(time.perf_counter()-t0)*1000:.0f}ms")
    return results


def search_hybrid(query: str, n_results: int = 10) -> list[dict]:
    """Combine semantic and BM25 results using Reciprocal Rank Fusion and return top-n passages."""
    sem_results = search_embeddings(query, n_results=n_results * 2)
    bm25_results = search_bm25(query, n_results=n_results * 2)

    k = 60
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for rank, r in enumerate(sem_results):
        doc_id = r['id']
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_map[doc_id] = r

    for rank, r in enumerate(bm25_results):
        doc_id = r['id']
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        if doc_id not in doc_map:
            doc_map[doc_id] = r

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n_results]
    return [doc_map[doc_id] for doc_id, _ in ranked]
