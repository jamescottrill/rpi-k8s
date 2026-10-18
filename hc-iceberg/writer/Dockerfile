# Multi-stage build for ARM64 (Raspberry Pi k3s cluster)
# Build stage handles any compiled dependencies cleanly.

FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim

LABEL org.opencontainers.image.title="iceberg-writer"
LABEL org.opencontainers.image.description="Shared Iceberg write service"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY main.py writer.py models.py registry.py personal_finance.py ./

# Directory for the SQLite catalogue DB (mount a PVC here in k8s)
RUN mkdir -p /data/catalogue

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
