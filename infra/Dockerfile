FROM python:3.12-slim

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation and non-buffered output
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Copy project manifest and configuration
COPY pyproject.toml uv.lock* ./
COPY config/ ./config/
COPY packages/ ./packages/
COPY apps/ ./apps/
COPY evals/ ./evals/

# Install application and all workspace members
RUN uv pip install --no-cache -e ./packages/contracts \
    -e ./packages/gateway \
    -e ./packages/identity \
    -e ./packages/routing/surface_policy \
    -e ./packages/routing/router \
    -e ./packages/routing/session \
    -e ./packages/personas/registry \
    -e ./packages/personas/runtime \
    -e ./packages/personas/tools_core \
    -e ./packages/personas/tools_impl \
    -e ./packages/safety/risk_classifier \
    -e ./packages/safety/approval \
    -e ./packages/memory/store \
    -e ./packages/memory/writer \
    -e ./packages/memory/retriever \
    -e ./packages/transparency/routing_log \
    -e ./packages/surfaces/telegram_slack \
    -e ./packages/surfaces/cli \
    -e ./apps/orchestrator \
    -e ./apps/api \
    -e ./evals

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
