FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TAX_AGENT_DB=/data/tax_agent.db

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.zh-CN.md ./
COPY tax_agent ./tax_agent
COPY rules ./rules
COPY mappings ./mappings
COPY templates ./templates
COPY schemas ./schemas

RUN pip install --no-cache-dir -e .

RUN mkdir -p /data /app/.data
VOLUME ["/data"]

EXPOSE 8790

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8790/health || exit 1

CMD ["tax-agent-api", "--host", "0.0.0.0", "--port", "8790"]
