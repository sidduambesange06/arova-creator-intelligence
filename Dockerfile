# Stage 1: Build Frontend SPA
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Engine Runtime
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

# Copy dependency manifests
COPY backend/pyproject.toml backend/uv.lock* /app/backend/

# Install python dependencies using uv
WORKDIR /app/backend
RUN uv pip install --system -r pyproject.toml

WORKDIR /app
COPY backend/app /app/backend/app
COPY mcp_server /app/mcp_server
COPY sample_data /app/sample_data
COPY docs /app/docs

# Copy built frontend assets
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

ENV PYTHONPATH="/app/backend:/app"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

