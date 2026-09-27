# ==============================================================================
# Stage 1: Build & Dependency Wheel Cache
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Pre-download FastEmbed model artifacts into cache
RUN PYTHONPATH=/install/lib/python3.11/site-packages python3 -c \
    "from fastembed import TextEmbedding; _ = TextEmbedding(model_name='BAAI/bge-small-en-v1.5')"

# ==============================================================================
# Stage 2: Minimal Production Runtime
# ==============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN groupadd -g 1001 cachemind && \
    useradd -u 1001 -g cachemind -s /bin/bash -m cachemind

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local
# Copy pre-downloaded FastEmbed model cache
COPY --from=builder /root/.cache /home/cachemind/.cache
RUN chown -R cachemind:cachemind /home/cachemind/.cache

# Copy application source code
COPY --chown=cachemind:cachemind . /app

USER cachemind

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    LOG_LEVEL=info \
    PORT=8000

EXPOSE 8000

# Health check configuration
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/v1/health || exit 1

# Production server entrypoint
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--access-log"]
