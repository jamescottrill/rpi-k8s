# Multi-stage build for ARM64 (Raspberry Pi k3s cluster).
# Plain Python image with no of-watchdog or HTTP server — the container runs
# scraper/runner.py once and exits, driven by a K8s CronJob.

FROM --platform=linux/arm64 python:3.12-slim AS builder

WORKDIR /build
COPY scraper/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM --platform=linux/arm64 python:3.12-slim

LABEL org.opencontainers.image.title="ascentric-scraper"
LABEL org.opencontainers.image.description="K8s CronJob: scrape Ascentric portfolio data and POST to iceberg-writer"

WORKDIR /app

COPY --from=builder /install /usr/local
COPY scraper/handler.py scraper/scraper.py scraper/runner.py ./

CMD ["python", "runner.py"]
