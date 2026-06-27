# Regulatory Intelligence Platform

Multi-agent platform that helps sales/solution architects and existing customers
validate requirements against product capabilities and assess release-driven
compliance/validation impact.

Built from the SpecKit in `medidata_ai_speckit_v3/`. See
[`docs/architecture.md`](docs/architecture.md) for the full picture.

## Architecture at a glance

```
React UI
  -> ASP.NET Core BFF + SignalR
  -> Apache Kafka  (runtime boundary: .NET <-> Python)
  -> Python Supervisor Harness  (LangGraph StateGraph)
       Orchestrator/Router - Planner - Memory Manager
       Model Gateway - Guardrails + HITL - Observability
  -> Independent LangGraph specialist agents
       Agile Master  -> Jira MCP
       Developer     -> GitHub MCP
       Research       -> Qdrant RAG MCP
       Document Analyst -> Custom Document MCP
Shared state: MongoDB (checkpoints/runs) - Qdrant (semantic memory) - S3 (artifacts)
```

The Supervisor delegates sub-tasks to independent agent graphs and aggregates
their structured results; it does not micromanage individual tool calls.

## Repository layout

| Path | What it is | Status |
|------|------------|--------|
| `libs/common` | Shared Python package: contracts, config, logging, Kafka, audit | ✅ implemented |
| `services/supervisor` | Shared Supervisor harness (LangGraph) | ✅ implemented |
| `services/agents/*` | Specialist agent graphs | ⏳ planned |
| `bff` | ASP.NET Core BFF + SignalR | ⏳ planned |
| `ui` | React client | ⏳ planned |
| `infra` | docker-compose for local Kafka/Mongo/Qdrant/S3 | ✅ |
| `docs` | Architecture & spec docs | ✅ |

Components are built one at a time. The **shared supervisor** is the first
implemented component.

## Quick start (Python tier)

```bash
# 1. Local infrastructure (Kafka, MongoDB, Qdrant, MinIO/S3)
docker compose -f infra/docker-compose.yml up -d

# 2. Install the Python workspace
cd services/supervisor
python -m venv .venv && source .venv/bin/activate
pip install -e ../../libs/common -e .[dev]

# 3. Run the supervisor in offline/fake mode (no AWS/Kafka needed)
APP_ENV=local MODEL_GATEWAY_MODE=fake python -m supervisor.app

# 4. Tests
pytest -q
```

`MODEL_GATEWAY_MODE=fake` and `KAFKA_MODE=memory` let the whole supervisor run
and be tested with no external dependencies.

## Configuration

All settings are environment-driven (see `libs/common/medidata_common/config.py`).
Key variables:

- `APP_ENV` — `local|dev|prod`
- `KAFKA_MODE` — `aiokafka|memory`
- `KAFKA_BOOTSTRAP_SERVERS`
- `MODEL_GATEWAY_MODE` — `bedrock|fake`
- `BEDROCK_MODEL_ID`, `AWS_REGION`
- `MONGODB_URI`, `MONGODB_DB`
- `CHECKPOINTER_MODE` — `mongodb|memory`

## License

Proprietary — internal use only.
