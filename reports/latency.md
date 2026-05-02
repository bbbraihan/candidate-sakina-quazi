# Sakina Health — Latency Report

**Generated:** 2026-05-02  
**Model:** `qwen2.5:7b-instruct` (local via Ollama)  
**Embedding model:** `BAAI/bge-small-en-v1.5`  
**Hardware:** Intel(R) Core(TM) i9-14900HX | 32 cores | 31.1 GB RAM | Linux x86_64 6.18.5-100.fc42.x86_64  
**Runs per stage:** 5  

> Each pipeline stage is timed over real queries from the eval dataset.
> A fixed WAV fixture (`dataset/fixture_query.wav`) is used for the STT stage
> so results are reproducible across runs.

---

## Pipeline Stages

| Stage | What it measures |
|-------|-----------------|
| `stt` | Speech-to-text: faster-whisper transcribing the fixture WAV |
| `retrieval` | ChromaDB vector search + embedding the query |
| `generation` | Local LLM generating the response (dominant stage) |
| `tts` | Text-to-speech: pyttsx3 synthesizing the reply text |
| `e2e (text)` | retrieval + generation only (text-only path) |
| `e2e (voice)` | Full voice round-trip: stt + retrieval + generation + tts |

**p50** = median (typical user experience).  
**p95** = 95th percentile (worst normal case).  
A large p50→p95 gap means high variance (e.g. occasional LLM stalls).

| Stage | Avg | p50 | p95 |
|-------|----:|----:|----:|
| stt | 718ms | 520ms | 1.34s |
| retrieval | 963ms | 22ms | 3.79s |
| generation | 18.31s | 18.11s | 21.25s |
| tts | 21ms | 14ms | 44ms |
| e2e (text: ret+gen) | 19.27s | 18.13s | 22.89s |
| e2e (voice: all) | 20.01s | 18.70s | 24.26s |

> Generation dominates total latency because the LLM runs fully on CPU.
> GPU inference or a smaller quantization (e.g. Q2_K) would reduce p95 significantly.
