# Delivery

## Installation

**Default models:**
- Chat/LLM: `qwen2.5:7b-instruct` (Ollama)
- Embedding: `BAAI/bge-small-en-v1.5` (HuggingFace)
- Speech-to-text: `faster-whisper base.en`

**1. Start the services:**
```bash
docker compose up --build
```

**2. Run document ingestion:**
```bash
docker exec -it sakina-app python -m sakina.embedding
```

**3. Access the chat UI:**

Open [https://localhost:8501](https://localhost:8501) in your browser.

> **Browser security warning:** The app uses a self-signed TLS certificate so that the browser grants microphone access (browsers block `getUserMedia` on plain HTTP). On first visit you will see a "Your connection is not private" warning. Click **Advanced → Proceed to localhost (unsafe)** to continue. This is expected and safe for local use.

---

## Design Decisions

### RAG Design

**Vector store: ChromaDB**  
ChromaDB runs in-process with a SQLite-backed persistent store — no separate server, no extra infra. For a corpus of ~263 chunks it is fast enough (retrieval p50 = 22ms).

**Chunking strategy**  
`BAAI/bge-small-en-v1.5` silently truncates input beyond 512 tokens. Without chunking, the second half of every long hadith (some reach 4,555 chars / ~1,138 tokens) is invisible to semantic search. Records over 1,600 characters are split with 200-character overlap so context carries across boundaries. Quran verses (~44 tokens on average) are not chunked — a verse is the minimal citable unit, and splitting it would break citation integrity.

**Hybrid search: BM25 + semantic with RRF**  
Pure vector search misses exact Arabic terms (*sabr*, *tawakkul*, *du'a*) and reference IDs (*Bukhari 6369*) because transliterated tokens sit far from anything else in embedding space. BM25 covers that lexical signal. Reciprocal Rank Fusion merges both rankings with no normalisation or parameter tuning — k=60 is robust across benchmarks. Result: hybrid Recall@5 = 0.52 vs BM25-only 0.35.

**Citations**  
Every response returns a structured `citations` JSON field with source IDs. The retriever deduplicates chunks from the same source before passing context to the LLM, so citations are unambiguous.

---

### Evaluation Framework

Each dimension is measured independently against a fixed dataset so results are reproducible and comparable across all four candidate models.

- **Recall** — 10 hand-labeled queries from `dataset/labels.json`; the retriever's top-k results are checked against expected passage IDs to compute Recall@3 and Recall@5.
- **Safety** — 14 adversarial prompts across 6 risk categories scored by a local LLM judge against a per-query behavior checklist (e.g. `provide_emergency_helpline`, `no_authoritative_ruling`); pass threshold ≥ 80/100. Queries in [`dataset/safety.jsonl`](dataset/safety.jsonl).
- **Faithfulness** — after each response the model's returned `citations` JSON is diffed against the retrieved chunk IDs; any citation not in the retrieved set is counted as a hallucination and the score is `matched / total`.
- **Latency** — p50/p95 per pipeline stage (STT, retrieval, generation, TTS) timed over 5 runs using a fixed WAV fixture for reproducible STT measurement.

Full results: [`reports/EVAL_COMPARISON.md`](reports/EVAL_COMPARISON.md) and [`reports/latency.md`](reports/latency.md).  
Summary: [`EVAL.md`](EVAL.md).

---

### Safety & Domain Handling

Safety is enforced at the system prompt level and verified empirically — the same adversarial queries used in evaluation are the ground truth for what the model must and must not do.

- **Crisis routing** — self-harm and suicidal ideation prompts must include emergency helpline info and must not rely on spiritual advice alone. Scored explicitly in the safety eval (a01, a05, a06).
- **No fabricated scripture** — the system prompt instructs the model to only cite what it was given; the faithfulness check flags any invented ID. Result: 1.00 faithfulness across all queries.
- **Fatwa refusal** — the system prompt explicitly forbids issuing religious rulings and instructs the model to defer to a qualified scholar.
- **Culturally aware tone** — responses must be empathetic and non-judgmental; religious guilt-shaming is a scored safety behavior.

---

### Voice Integration

- **STT: `faster-whisper`** — roughly 4× faster than `openai-whisper` on CPU at the same accuracy. Default model `base.en`, `int8` compute, CPU. Override via `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`.
- **TTS: `pyttsx3`** — no model download, works on macOS/Linux/Windows. Trade-off: robotic audio quality. Replace the body of `synthesize()` in `sakina/voice.py` with Piper (ONNX) for natural-sounding speech.
- **Error handling** — every voice call returns `(result, error)`. Empty/garbled transcripts surface a warning instead of firing the LLM. TTS failure degrades gracefully — text still renders, audio silently skipped.

---

### Code Quality & Structure

Clear module split, all files fully typed and documented:

| Module | Responsibility |
|--------|---------------|
| `sakina/search.py` | Retrieval — BM25, semantic, hybrid RRF |
| `sakina/chat.py` | Generation — system prompt, context building, citation extraction |
| `sakina/eval/` | Evaluation harness — recall, faithfulness, safety, latency |
| `sakina/voice.py` | Voice I/O — STT (faster-whisper) and TTS (pyttsx3) |
| `sakina/embedding.py` | Ingestion — chunking and ChromaDB upsert |
| `sakina/config.py` | Single source of truth for all env vars |

---

### Production Thinking

- All config via environment variables; no hardcoded paths or secrets. See `.env.example` for all overridable vars.
- `loguru` structured logging on every request: prompt, retrieved chunk IDs, response, latency, and token count.
- Graceful fallback when STT, TTS, or the LLM fails — each subsystem returns `(result, error)` so the UI degrades without crashing.
- ChromaDB path, Ollama host, model names, Whisper settings, and TTS rate are all overridable at runtime.

---

### Model Choice

`qwen2.5:7b-instruct` was chosen after running the full eval across all four candidate models:

| Model | Recall@5 | Safety | Pass | Faithfulness |
|-------|:--------:|:------:|:----:|:------------:|
| **qwen2.5:7b-instruct** | 0.45 | **80/100** | **8/14** | 1.00 |
| llama3.1:8b-instruct-q4_K_M | 0.45 | 77/100 | 7/14 | 1.00 |
| mistral:7b-instruct | 0.45 | 77/100 | 7/14 | 0.83 |
| gemma2:9b-instruct-q4_K_M | 0.45 | 77/100 | 7/14 | 1.00 |

qwen2.5 scored highest on safety (80/100, 8/14 pass) — the most critical dimension for a mental health app. Recall and faithfulness are equal to llama3.1 and gemma2. Mistral was ruled out due to lower faithfulness (hallucinated citation IDs on one query). qwen2.5 also carries an Apache 2.0 license and shows strong instruction-following at Q4_K_M quantization.

---

## Evaluation

All results are written to `./reports/` (bind-mounted into the container).

Adversarial safety queries are sourced from [`dataset/safety.jsonl`](dataset/safety.jsonl).

**Default model** — recall, safety, faithfulness, and latency for `qwen2.5:7b-instruct`:
```bash
docker exec -it sakina-app python -m sakina.eval --default-model
```

**All models** — same tasks across all models in `config.CHAT_MODELS`:
```bash
docker exec -it sakina-app python -m sakina.eval --all-models
```

**Latency** — p50/p95 benchmarks for each pipeline stage:
```bash
docker exec -it sakina-app python -m sakina.eval --latency
```

> **Note:** `--all-models` requires all four models to be pulled first:
> ```bash
> docker exec -it sakina-ollama ollama pull qwen2.5:7b-instruct
> docker exec -it sakina-ollama ollama pull llama3.1:8b-instruct-q4_K_M
> docker exec -it sakina-ollama ollama pull mistral:7b-instruct
> docker exec -it sakina-ollama ollama pull gemma2:9b-instruct-q4_K_M
> ```
> `--default-model` and `--latency` only need `qwen2.5:7b-instruct`.

### Report Files

| File | What it contains |
|------|-----------------|
| `reports/EVAL_REPORT.md` | Full report for the default model (recall, safety, faithfulness, latency) |
| `reports/EVAL_REPORT_LOG.md` | Raw console output from the `--default-model` run |
| `reports/EVAL_COMPARISON.md` | Side-by-side comparison of all 4 models |
| `reports/EVAL_COMPARISON_LOG.md` | Raw console output from the `--all-models` run |
| `reports/latency.md` | p50/p95 latency benchmarks |
| `reports/latency_log.md` | Raw console output from the `--latency` run |
