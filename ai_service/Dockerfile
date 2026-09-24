# FastAPI AI microservice.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app

RUN addgroup --system ai && adduser --system --ingroup ai ai
USER ai

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8001/health || exit 1

# A single async worker: the service is I/O bound, so extra processes only add
# memory. Scale horizontally instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
