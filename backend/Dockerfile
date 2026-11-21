# syntax=docker/dockerfile:1
# Build from the repository root:  docker build -f backend/Dockerfile -t ul-navigator-api .
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/data/hf-cache DATA_DIR=/app/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-ml.txt ./
# CPU-only PyTorch keeps the image ~1 GB smaller than the default CUDA wheels
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt -r requirements-ml.txt "psycopg[binary]==3.3.9"
COPY backend ./backend
COPY ingestion ./ingestion
RUN useradd --create-home --uid 10001 app && mkdir -p /app/data && chown -R app /app
USER app
WORKDIR /app/backend
ENV PYTHONPATH=/app/backend:/app/ingestion
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
