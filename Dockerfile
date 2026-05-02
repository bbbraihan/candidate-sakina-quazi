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
        build-essential \
        openssl

RUN openssl req -x509 -newkey rsa:2048 -keyout /app/ssl.key -out /app/ssl.crt \
    -days 3650 -nodes -subj "/CN=localhost"

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/reports

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request, ssl; urllib.request.urlopen('https://localhost:8501/_stcore/health', context=ssl._create_unverified_context())"

CMD ["streamlit", "run", "sakina/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.sslCertFile=/app/ssl.crt", \
     "--server.sslKeyFile=/app/ssl.key"]
