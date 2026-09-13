FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 8000

# On boot: build the index if it's missing/empty, then start the API.
# This is what makes `docker compose up` a genuine one-command startup (PRD/README §5).
CMD ["sh", "-c", "\
    if [ ! -s /app/data/index.db ]; then \
      echo '[entrypoint] No index found — ingesting transcripts (first boot only)...'; \
      python scripts/ingest_transcripts.py || echo '[entrypoint] Ingestion failed — starting anyway, /health/ready will report it.'; \
    fi; \
    uvicorn app.main:app --host 0.0.0.0 --port 8000 \
"]
