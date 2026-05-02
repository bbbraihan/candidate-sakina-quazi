# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

# System deps:
#   espeak-ng  — pyttsx3 TTS on Linux
#   libsndfile1, ffmpeg — audio I/O for faster-whisper / streamlit-mic-recorder
#   build-essential — native extensions (faiss-cpu, chroma)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        espeak-ng \
        libsndfile1 \
        ffmpeg \
        build-essential

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/reports

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["streamlit", "run", "sakina/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
