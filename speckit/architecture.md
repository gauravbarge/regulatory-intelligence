# Architecture Specification

## High-Level Architecture

```text
React UI
  |
ASP.NET Core BFF + SignalR
  |
Apache Kafka runtime boundary
  |
Python Supervisor Harness
  |-- Orchestrator / Router
  |-- Planner
  |-- Memory Manager
  |-- Model Gateway
  |-- Guardrails + HITL
  |-- Observability
  |
Independent LangGraph Agents
  |-- Agile Master Agent -> Jira MCP
  |-- Developer Agent -> GitHub MCP
  |-- Research Agent -> Qdrant RAG
  |-- Document Analyst Agent -> Custom Document MCP
```

## Key Design Change in v3
Each specialist agent is not a simple tool. Each is its own compiled LangGraph graph with:
- Internal state
- Reason → Act → Observe loop
- Tool-specific retries
- Agent-level memory recall
- Structured output contract

The Supervisor does not micromanage every tool call. It delegates sub-tasks to agent graphs and aggregates final agent results.

## Runtime Boundary

Kafka topics:
- `task.request`
- `agent.dispatch`
- `agent.result`
- `ui.inbound.response`
- `tool.call.event`
- `dead.letter`
- `audit.event`

## Shared State

### MongoDB
- LangGraph checkpoints
- conversation/thread state
- execution run records
- approval status

### Qdrant
- product documentation embeddings
- release notes
- validation artifacts
- SOPs
- RTMs
- semantic memory

### Amazon S3
- uploaded customer RFPs
- generated reports
- validation evidence packages
- raw documents
- long-form artifacts

## Communication Model
- UI streams request to BFF.
- BFF writes task to Kafka.
- Supervisor consumes task and creates execution plan.
- Supervisor dispatches agent-specific sub-tasks.
- Agents execute independently and return structured findings.
- Supervisor synthesizes final response.
- Guardrails determine whether human approval is required.
- BFF streams final response and artifacts to UI.
