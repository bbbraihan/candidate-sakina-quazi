#!/usr/bin/env python3
"""
Sakina Voice I/O - Local STT (faster-whisper) and TTS (pyttsx3).

All models run locally; no paid APIs. Each public function returns
(result, error) so callers can gracefully fall back to text-only mode.
"""

from __future__ import annotations

import io
import os
import platform
import subprocess
import tempfile
import time
import wave
from typing import Any

from loguru import logger
from . import config

_WHISPER_MODEL: Any | None = None


def _get_whisper() -> Any:
    """Lazy-load faster-whisper. Configurable via env."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    from faster_whisper import WhisperModel

    model_size = config.WHISPER_MODEL
    device = config.WHISPER_DEVICE
    compute_type = config.WHISPER_COMPUTE_TYPE

    logger.info(f"Loading faster-whisper model={model_size} device={device} compute={compute_type}")
    _WHISPER_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _WHISPER_MODEL


def transcribe(audio_bytes: bytes) -> tuple[str | None, str | None]:
    """Transcribe WAV/PCM audio bytes to text.

    Returns (text, error). On failure, text is None and error holds a message
    suitable for logging or showing the user.
    """
    if not audio_bytes:
        return None, "empty audio"

    start = time.time()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        model = _get_whisper()
        segments, info = model.transcribe(tmp_path, beam_size=1, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()

        latency = time.time() - start
        logger.info(f"STT ok: {len(text)} chars, {latency:.2f}s, lang={info.language}")

        if not text:
            return None, "no speech detected"
        return text, None
    except Exception as e:
        logger.exception("STT failed")
        return None, f"transcription failed: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _synthesize_macos(text: str) -> tuple[bytes | None, str | None]:
    """Use macOS `say` + `afconvert` to produce a real WAV file.

    pyttsx3's NSSpeechSynthesizer backend emits AIFF even when the output
    filename ends in .wav, which Streamlit's audio widget can't decode.
    """
    aiff_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            aiff_path = tmp.name
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name

        subprocess.run(
            ["say", "-r", str(config.TTS_RATE), "-o", aiff_path, text],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff_path, wav_path],
            check=True,
            capture_output=True,
        )
        with open(wav_path, "rb") as f:
            return f.read(), None
    finally:
        for p in (aiff_path, wav_path):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass


def synthesize(text: str) -> tuple[bytes | None, str | None]:
    """Synthesize text to WAV audio bytes.

    Returns (wav_bytes, error). On failure, bytes are None.
    """
    if not text or not text.strip():
        return None, "empty text"

    start = time.time()
    try:
        if platform.system() == "Darwin":
            data, err = _synthesize_macos(text)
            if err:
                return None, err
        else:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", config.TTS_RATE)

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                engine.save_to_file(text, tmp_path)
                engine.runAndWait()
                engine.stop()
                with open(tmp_path, "rb") as f:
                    data = f.read()
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        if not data:
            return None, "tts produced empty audio"

        try:
            with wave.open(io.BytesIO(data), "rb"):
                pass
        except wave.Error:
            return None, "tts output is not a valid WAV"

        latency = time.time() - start
        logger.info(f"TTS ok: {len(data)} bytes, {latency:.2f}s")
        return data, None
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        logger.exception("TTS subprocess failed")
        return None, f"synthesis failed: {stderr or e}"
    except Exception as e:
        logger.exception("TTS failed")
        return None, f"synthesis failed: {e}"
