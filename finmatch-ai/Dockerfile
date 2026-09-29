# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build stage: install the application and its dependencies into a virtualenv
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install .

# ---------------------------------------------------------------------------
# Runtime stage: slim image, non-root user, no build tooling, no secrets
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    FINMATCH_ENVIRONMENT=production \
    FINMATCH_INVESTOR_DATA_PATH=/app/data/investor_mandates.json

RUN groupadd --system --gid 10001 finmatch \
    && useradd --system --uid 10001 --gid finmatch --no-create-home \
       --shell /usr/sbin/nologin finmatch

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# Data stays root-owned: the application user can read it but not modify it.
COPY data ./data

USER finmatch

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3).status == 200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
