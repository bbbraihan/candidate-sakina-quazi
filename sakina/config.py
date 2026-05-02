"""
Sakina Health configuration — all values are overridable via environment variables.
Validated at import time so misconfiguration fails fast with a clear message.
"""

from __future__ import annotations

import os

CHAT_MODEL: str = os.environ.get("CHAT_MODEL", "qwen2.5:7b-instruct")
EMBED_MODEL: str = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "base.en")
WHISPER_DEVICE: str = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE: str = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

TTS_RATE: int = int(os.environ.get("TTS_RATE", "175"))

CHAT_MODELS: list[str] = [
    "qwen2.5:7b-instruct",
    "llama3.1:8b-instruct-q4_K_M",
    "mistral:7b-instruct",
    "gemma2:9b-instruct-q4_K_M",
]

JUDGE_MODEL: str = os.environ.get("JUDGE_MODEL", "qwen2.5:7b-instruct")
CHROMA_PATH: str = os.environ.get("CHROMA_PATH", "./chroma_db")

# --- Validation (fail fast on misconfiguration) ---

_VALID_WHISPER_DEVICES: set[str] = {"cpu", "cuda", "auto"}
if WHISPER_DEVICE not in _VALID_WHISPER_DEVICES:
    raise ValueError(
        f"Invalid WHISPER_DEVICE={WHISPER_DEVICE!r}. "
        f"Must be one of {sorted(_VALID_WHISPER_DEVICES)}."
    )

_VALID_COMPUTE_TYPES: set[str] = {"int8", "int8_float16", "int16", "float16", "float32", "default"}
if WHISPER_COMPUTE_TYPE not in _VALID_COMPUTE_TYPES:
    raise ValueError(
        f"Invalid WHISPER_COMPUTE_TYPE={WHISPER_COMPUTE_TYPE!r}. "
        f"Must be one of {sorted(_VALID_COMPUTE_TYPES)}."
    )

if not (50 <= TTS_RATE <= 400):
    raise ValueError(
        f"TTS_RATE={TTS_RATE} is outside the valid range [50, 400] words per minute."
    )

if not CHROMA_PATH.strip():
    raise ValueError("CHROMA_PATH must not be empty.")
