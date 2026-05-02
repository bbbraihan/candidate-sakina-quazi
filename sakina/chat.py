#!/usr/bin/env python3
"""
Sakina Health Chat CLI - Interactive spiritual guidance with citations
"""

from __future__ import annotations

import time
from loguru import logger
import ollama
from ollama import ResponseError
from html import escape
from . import config
from .search import search_embeddings, search_hybrid
from .prompts import (
    SYSTEM_PROMPT, CLASSIFIER_PROMPT, get_user_prompt,
    INTENT_CATEGORIES, OUT_OF_SCOPE_MARKERS,
    CRISIS_RESPONSE_TEMPLATE, SELF_HARM_RESPONSE, INJECTION_RESPONSE,
    SECTARIAN_RESPONSE, FATWA_RESPONSE, MEDICAL_RESPONSE,
    HALLUCINATION_BAIT_RESPONSE, OUT_OF_SCOPE_RESPONSE,
)
from pydantic import BaseModel, Field

MAX_RETRIES: int = 2


SAFE_RESPONSES: dict[str, str] = {
    "crisis":            CRISIS_RESPONSE_TEMPLATE,
    "self_harm":         SELF_HARM_RESPONSE,
    "prompt_injection":  INJECTION_RESPONSE,
    "sectarian":         SECTARIAN_RESPONSE,
    "fatwa":             FATWA_RESPONSE,
    "medical":           MEDICAL_RESPONSE,
    "hallucination_bait": HALLUCINATION_BAIT_RESPONSE,
    "out_of_scope":      OUT_OF_SCOPE_RESPONSE,
}

class IntentClassification(BaseModel):
    intent: str = Field(description="The classified intent category")
    confidence: float = Field(description="Confidence score 0-1")
    reasoning: str = Field(description="Brief reasoning for classification")


def classify_intent(query: str) -> IntentClassification:
    """Classify a user query into a safety/intent category using a structured LLM call."""
    t0 = time.perf_counter()
    for attempt in range(MAX_RETRIES):
        try:
            resp = ollama.chat(
                model=config.CHAT_MODEL,
                messages=[
                    {"role": "system", "content": CLASSIFIER_PROMPT},
                    {"role": "user", "content": query},
                ],
                options={"temperature": 0, "num_predict": 300, "num_ctx": 4096},
                format=IntentClassification.model_json_schema(),
            )
            result = IntentClassification.model_validate_json(resp.message.content)
            logger.info(
                f"classify: intent={result.intent} confidence={result.confidence:.2f} "
                f"attempt={attempt+1} latency_ms={int((time.perf_counter()-t0)*1000)}"
            )
            return result
        except ResponseError as e:
            if e.status_code == 404:
                logger.error(
                    f"classifier attempt {attempt+1}/{MAX_RETRIES} failed: model '{config.CHAT_MODEL}' not found — "
                    f"pull it with: docker exec -it sakina-ollama ollama pull {config.CHAT_MODEL}"
                )
            else:
                logger.error(f"classifier attempt {attempt+1}/{MAX_RETRIES} failed (status {e.status_code}): {e}")
            continue
        except Exception as e:
            logger.error(f"classifier attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
            continue

    # Fallback: crisis is the safest default — better to over-triage than miss a real crisis
    logger.warning(
        f"classifier exhausted {MAX_RETRIES} retries, falling back to crisis "
        f"latency_ms={int((time.perf_counter()-t0)*1000)}"
    )
    return IntentClassification(
        intent="crisis", confidence=0.0, reasoning="classifier_failed"
    )

class SpiritualGuidanceResponse(BaseModel):
    response: str = Field(description="The compassionate response addressing the person's spiritual question")
    citations: list[str] = Field(description="List of document IDs that were actually cited in the response")


def build_context(retrieved_passages: list[dict]) -> tuple[str, list[str]]:
    """Convert retrieved passages into an XML context block and a deduplicated list of document IDs."""
    documents = []
    document_ids = []
    seen_ids: set[str] = set()

    for passage in retrieved_passages:
        doc_id = str(passage.get("id", ""))
        # Deduplicate: when chunking is active, multiple chunks from the same
        # source record share the same metadata 'id'. Keep only the first
        # (highest-similarity) chunk so the LLM receives one citation target.
        if doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)
        if doc_id:
            document_ids.append(doc_id)

        metadata = []
        for key, value in passage.items():
            if key in ("document", "chunk_index"):
                continue
            metadata.append(f"<{key}>{escape(str(value))}</{key}>")

        content = escape(str(passage.get("document", "")))
        documents.append(
            "<document>"
            f"<metadata>{''.join(metadata)}</metadata>"
            f"<content>{content}</content>"
            "</document>"
        )

    return f"<documents>{''.join(documents)}</documents>", document_ids




# -----------------------------
# MAIN ROUTER
# -----------------------------

def generate_response_with_citations(user_query: str, retrieved_passages: list[dict]) -> dict[str, str | list[str]]:
    """
    Classify intent, apply safety routing, then generate a structured response with citations.

    Returns a dict with keys: response, citations, retrieved_document_ids, raw_citations.
    Safe-response categories (crisis, fatwa, etc.) bypass the LLM and return canned text.
    """
    logger.debug(user_query)

    _safe = {"citations": [], "retrieved_document_ids": [], "raw_citations": []}

    # -------------------------
    # LLM CLASSIFIER (single safety gate)
    # -------------------------
    intent = classify_intent(user_query)
    logger.info(f"Intent: {intent.intent} (confidence: {intent.confidence})")

    if intent.intent in SAFE_RESPONSES:
        return {"response": SAFE_RESPONSES[intent.intent], **_safe}

    context, context_document_ids = build_context(retrieved_passages)
    retrieved_document_ids = context_document_ids

    user_prompt = get_user_prompt(user_query, context)

    for attempt in range(MAX_RETRIES):
        t_gen = time.perf_counter()
        try:
            resp = ollama.chat(
                model=config.CHAT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                        + "\n\nReturn only valid JSON as required."
                    },
                    {"role": "user", "content": user_prompt}
                ],
                options={
                    "temperature": 0,
                    "num_predict": 1200,
                    "num_ctx": 8192,
                },
                format=SpiritualGuidanceResponse.model_json_schema()
            )

            content = SpiritualGuidanceResponse.model_validate_json(
                resp.message.content
            )

            response = content.response

            raw_citations = content.citations or []
            citations = [
                c for c in raw_citations if c in context_document_ids
            ]

            # Clear citations on out-of-scope refusals (LLM sometimes cites despite refusing)
            r = response.lower()
            if any(m in r for m in OUT_OF_SCOPE_MARKERS):
                citations = []

            logger.info(
                f"generate: citations={len(citations)} raw={len(raw_citations)} "
                f"attempt={attempt+1} latency_ms={int((time.perf_counter()-t_gen)*1000)}"
            )
            return {
                "response": response,
                "citations": citations,
                "retrieved_document_ids": retrieved_document_ids,
                "raw_citations": raw_citations,
            }

        except ResponseError as e:
            if e.status_code == 404:
                logger.error(
                    f"LLM generation attempt {attempt+1}/{MAX_RETRIES} failed: model '{config.CHAT_MODEL}' not found — "
                    f"pull it with: docker exec -it sakina-ollama ollama pull {config.CHAT_MODEL}"
                )
            else:
                logger.error(
                    f"LLM generation attempt {attempt+1}/{MAX_RETRIES} failed (status {e.status_code}) "
                    f"latency_ms={int((time.perf_counter()-t_gen)*1000)}: {e}"
                )
            continue
        except Exception as e:
            logger.error(
                f"LLM generation attempt {attempt+1}/{MAX_RETRIES} failed "
                f"latency_ms={int((time.perf_counter()-t_gen)*1000)}: {e}"
            )
            continue

    # FALLBACK
    logger.warning(f"generation exhausted {MAX_RETRIES} retries, returning fallback response")
    return {
        "response": (
            "I'm sorry, I couldn't generate a reliable response this time.\n\n"
            "If this is urgent or you're in distress, please reach out to someone you trust or a qualified professional."
        ),
        "citations": [],
        "retrieved_document_ids": retrieved_document_ids,
        "raw_citations": [],
    }


def generate_response(user_query: str) -> tuple[str, list[str], list[str], list[str]]:
    """Run the full RAG pipeline: hybrid search → response generation → citation filtering.

    Returns (response_text, filtered_citations, retrieved_document_ids, raw_citations).
    """
    search_results = search_hybrid(user_query, n_results=10)
    resp = generate_response_with_citations(user_query, search_results)
    return resp['response'], resp['citations'], resp['retrieved_document_ids'], resp['raw_citations']


def main() -> None:
    """Interactive CLI loop for testing the chat pipeline."""
    while True:
        try:
            user_query = input("You: ").strip()

            if user_query.lower() in ['quit', 'exit', 'q']:
                break

            if not user_query:
                continue

            response, citations, retrieved_document_ids, _ = generate_response(user_query)

            print(response)
            print("\nCitations:")
            print(citations)
            print("\nRetrieved Document IDs:")
            print(retrieved_document_ids)

            print("\n" + "-"*60)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            print("Please try again.\n")


if __name__ == "__main__":
    main()
