# Arova Creator Intelligence — Backend & MCP Engine Container
# Lightweight, reproducible Python runtime. Exposes REST API and MCP services.
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

# Copy project manifests
COPY backend/pyproject.toml backend/uv.lock /app/backend/

# Install locked dependencies into project virtual environment
WORKDIR /app/backend
RUN uv sync --no-dev --locked

WORKDIR /app
COPY backend/app /app/backend/app
COPY mcp_server /app/mcp_server
COPY sample_data /app/sample_data
COPY docs /app/docs

ENV PYTHONPATH="/app/backend:/app"
ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
