"""
Latency benchmarking — per-stage timing across the full Sakina pipeline.
"""

from __future__ import annotations

import json
import os
import platform
import time
from typing import Any


def _get_hardware_info() -> str:
    """Return a human-readable hardware summary for the latency report."""
    cpu = platform.processor()
    if not cpu and platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        cpu = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass
    cpu = cpu or platform.machine()

    cores = os.cpu_count() or "?"

    ram_gb: float | str = "?"
    if platform.system() == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        ram_gb = round(int(line.split()[1]) / 1024 / 1024, 1)
                        break
        except OSError:
            pass

    return (
        f"{cpu} | {cores} cores | {ram_gb} GB RAM | "
        f"{platform.system()} {platform.machine()} {platform.release()}"
    )


def _percentile(data: list[float], pct: float) -> float:
    """Return the pct-th percentile of a list using linear interpolation."""
    s = sorted(data)
    k = (len(s) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _fmt(val: float) -> str:
    """Format a duration in seconds as 's' or 'ms' depending on magnitude."""
    return f"{val:.2f}s" if val >= 1.0 else f"{val * 1000:.0f}ms"


def eval_latency(n_runs: int = 5) -> dict[str, Any]:
    """Measure p50/p95 latency for each pipeline stage over n_runs queries."""
    from sakina.search import search_embeddings
    from sakina.chat import generate_response_with_citations
    from sakina.voice import transcribe, synthesize

    with open("dataset/labels.json", "r", encoding="utf-8") as f:
        queries = json.load(f)["queries"]

    fixture_path = "dataset/fixture_query.wav"
    with open(fixture_path, "rb") as f:
        fixture_wav = f.read()

    TTS_SAMPLE = (
        "Anxiety is a challenge many face. Islam offers guidance through "
        "patience, prayer, and trusting in Allah's wisdom. The Quran reminds "
        "us that with hardship comes ease, so hold on with hope."
    )

    t_stt, t_retrieval, t_generation, t_tts = [], [], [], []
    t_e2e_text, t_e2e_voice = [], []

    print(f"Running {n_runs} latency samples (this will take a while)...\n")

    for i in range(n_runs):

        query = queries[i % len(queries)]["query"]

        t0 = time.perf_counter()
        transcribe(fixture_wav)
        stt = time.perf_counter() - t0
        t_stt.append(stt)

        t0 = time.perf_counter()
        passages = search_embeddings(query, n_results=10)
        ret = time.perf_counter() - t0
        t_retrieval.append(ret)

        t0 = time.perf_counter()
        generate_response_with_citations(query, passages)
        gen = time.perf_counter() - t0
        t_generation.append(gen)

        t0 = time.perf_counter()
        synthesize(TTS_SAMPLE)
        tts = time.perf_counter() - t0
        t_tts.append(tts)

        t_e2e_text.append(ret + gen)
        t_e2e_voice.append(stt + ret + gen + tts)

        print(
            f"  [{i+1:>2}/{n_runs}] "
            f"stt={_fmt(stt)} ret={_fmt(ret)} gen={_fmt(gen)} tts={_fmt(tts)}"
        )

    hw = _get_hardware_info()
    print(f"\n# Hardware: {hw}\n")
    print(f"{'Stage':<22} {'avg':>8} {'p50':>8} {'p95':>8}")
    print("-" * 50)

    stage_data = {
        "stt": t_stt,
        "retrieval": t_retrieval,
        "generation": t_generation,
        "tts": t_tts,
        "e2e_text": t_e2e_text,
        "e2e_voice": t_e2e_voice,
    }
    stages = {}
    for label, data in stage_data.items():
        avg = sum(data) / len(data)
        p50 = _percentile(data, 50)
        p95 = _percentile(data, 95)
        stages[label] = {"avg": avg, "p50": p50, "p95": p95}
        display = label.replace("_", " ").replace("e2e text", "e2e (text: ret+gen)").replace("e2e voice", "e2e (voice: all)")
        print(f"{display:<22} {_fmt(avg):>8} {_fmt(p50):>8} {_fmt(p95):>8}")

    return {"hardware": hw, "n_runs": n_runs, "stages": stages}
