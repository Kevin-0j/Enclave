# Enclave API. Build context is the repo root (see compose.yaml).
FROM python:3.12.16-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12.16-slim-bookworm
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin enclave
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY --chmod=0644 api/alembic.ini ./
COPY --chmod=0755 api/alembic/ ./alembic/
COPY --chmod=0755 api/app/ ./app/
COPY --chmod=0644 sim/cameras.json ./cameras.json
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER enclave
EXPOSE 8000
# Proxy headers are only trusted from Caddy's fixed address on the edge network.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "172.31.251.10", "--no-server-header"]
