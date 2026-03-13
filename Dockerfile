FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LOOM_DATABASE_URL=sqlite:////app/data/loom.db \
    LOOM_UI_AUTH_MODE=none

RUN apt-get update && apt-get install -y --no-install-recommends \
    git gh curl jq sqlite3 default-jre nodejs npm graphviz postgresql-client ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY loom ./loom
COPY tests ./tests
COPY scripts ./scripts

RUN pip install --upgrade pip && pip install -e .[dev,integrations]

RUN useradd -m loomuser
RUN mkdir -p /app/data && chown -R loomuser:loomuser /app
USER loomuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["loom", "--serve"]
