FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

FROM base AS deps
WORKDIR /build
COPY libs/common /build/libs/common
RUN pip install --no-cache-dir /build/libs/common

COPY services/agile_master_agent/pyproject.toml /build/agile_master_agent/
WORKDIR /build/agile_master_agent
RUN pip install --no-cache-dir ".[jira,bedrock]"

FROM base AS runtime
WORKDIR /app

COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY services/agile_master_agent/agile_master_agent /app/agile_master_agent

RUN chown -R appuser:appgroup /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import agile_master_agent; print('ok')" || exit 1

ENTRYPOINT ["python", "-m", "agile_master_agent.app"]
