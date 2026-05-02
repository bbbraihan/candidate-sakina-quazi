"""
Sakina Health embedding ingestion — chunks and upserts Quran, hadith, and article datasets
into a ChromaDB collection using BGE-small-en-v1.5 embeddings.
"""

from __future__ import annotations

import json

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from loguru import logger
from sentence_transformers import SentenceTransformer

from .config import CHROMA_PATH, EMBED_MODEL

QURAN_META_KEYS: list[str]   = ['id', 'source', 'reference', 'surah', 'ayah', 'theme']
HADITH_META_KEYS: list[str]  = ['id', 'source', 'reference', 'number', 'chapter', 'theme']
ARTICLE_META_KEYS: list[str] = ['id', 'title', 'theme']

# BGE-small-en-v1.5 has a hard 512-token limit; ~4 chars/token → 1600 chars ≈ 400 tokens.
# Content beyond this is silently truncated during embedding, making it unretrievable.
# Overlap preserves semantic continuity across chunk boundaries.
CHUNK_CHAR_LIMIT: int = 1600
CHUNK_OVERLAP: int    = 200


class BGEEmbeddingFunction(EmbeddingFunction):
    """ChromaDB-compatible embedding function backed by a SentenceTransformer model."""

    model: SentenceTransformer

    def __init__(self, model_name: str) -> None:
        """Load the SentenceTransformer model by name."""
        self.model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        """Encode a batch of documents and return their embeddings as a list."""
        return self.model.encode(input).tolist()


def chunk_document(record_id: str, text: str, meta: dict[str, str]) -> list[tuple[str, str, dict[str, str]]]:
    """Split a document into overlapping chunks that fit within the BGE token limit.

    Returns a list of (chunk_id, chunk_text, chunk_metadata) tuples.
    Short documents that fit in one chunk are returned as-is.
    """
    if len(text) <= CHUNK_CHAR_LIMIT:
        return [(record_id, text, meta)]

    chunks = []
    start, i = 0, 0
    while start < len(text):
        end = min(start + CHUNK_CHAR_LIMIT, len(text))
        chunk_meta = {**meta, "chunk_index": str(i)}
        chunks.append((f"{record_id}_chunk_{i}", text[start:end], chunk_meta))
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP
        i += 1

    return chunks


def parse_record(doc_path: str, data: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Build the embedding text and metadata dict for a single JSONL record.

    Returns (text_for_embedding, metadata_dict).
    The text format differs per source type (Quran, Hadith, Article).
    """
    if doc_path == "dataset/quran.jsonl":
        text = (
            f"Theme: {data.get('theme', 'N/A')}\n"
            f"Text: {data.get('text', 'N/A')}"
        )
        meta = {k: str(data.get(k, "N/A")) for k in QURAN_META_KEYS}
        meta['source_type'] = 'Quran'

    elif doc_path == "dataset/hadith.jsonl":
        text = (
            f"Chapter: {data.get('chapter', 'N/A')}\n"
            f"Theme: {data.get('theme', 'N/A')}\n"
            f"Text: {data.get('text', 'N/A')}"
        )
        meta = {k: str(data.get(k, "N/A")) for k in HADITH_META_KEYS}
        meta['source_type'] = 'Hadith'

    else:  # articles
        text = (
            f"Title: {data.get('title', 'N/A')}\n"
            f"Theme: {data.get('theme', 'N/A')}\n"
            f"Text: {data.get('text', 'N/A')}"
        )
        meta = {k: str(data.get(k, "N/A")) for k in ARTICLE_META_KEYS}
        meta['source_type'] = 'Article'

    return text, meta


if __name__ == "__main__":
    logger.info(f"Initializing embedding function with model: {EMBED_MODEL}")
    embed_fn: BGEEmbeddingFunction = BGEEmbeddingFunction(EMBED_MODEL)

    logger.info("Connecting to ChromaDB client")
    client: chromadb.PersistentClient = chromadb.PersistentClient(path=CHROMA_PATH)

    logger.info("Getting or creating collection: sakina_content")
    collection: chromadb.Collection = client.get_or_create_collection("sakina_content", embedding_function=embed_fn)

    BATCH_SIZE: int = 4

    logger.info("Starting ingestion of all datasets into unified collection 'sakina_content'")

    batch_ids: list[str] = []
    batch_docs: list[str] = []
    batch_metas: list[dict[str, str]] = []
    total_processed: int = 0

    for doc_path in ["dataset/quran.jsonl", "dataset/hadith.jsonl", "dataset/articles.jsonl"]:
        logger.info(f"Processing {doc_path}...")

        with open(doc_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                data = json.loads(line)
                text, meta = parse_record(doc_path, data)

                record_id = data.get('id', None)
                if record_id is None:
                    logger.error(f"Record on line {line_no} in {doc_path} is missing 'id' field")
                    raise ValueError(f"Record on line {line_no} in {doc_path} is missing 'id' field.")

                for chunk_id, chunk_text, chunk_meta in chunk_document(record_id, text, meta):
                    batch_ids.append(chunk_id)
                    batch_docs.append(chunk_text)
                    batch_metas.append(chunk_meta)
                    total_processed += 1

                    if len(batch_ids) >= BATCH_SIZE:
                        try:
                            collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
                            logger.debug(f"Upserted batch (total processed: {total_processed})")
                            batch_ids, batch_docs, batch_metas = [], [], []
                        except Exception as e:
                            logger.error(f"Failed to upsert batch: {e}")
                            raise

    if batch_ids:
        try:
            collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
            logger.debug(f"Upserted final batch (total processed: {total_processed})")
        except Exception as e:
            logger.error(f"Failed to upsert final batch: {e}")
            raise

    final_count = collection.count()
    logger.success(f"Ingestion complete! Collection 'sakina_content' now has {final_count} records")
