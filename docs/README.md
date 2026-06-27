# Medidata Regulatory Intelligence Platform – SpecKit v3

Production-ready SpecKit for an AI coding agent/team to implement the multi-agent platform.

## Core Architecture

- **UI Client:** React
- **BFF:** ASP.NET Core + SignalR streaming
- **Runtime Boundary:** Apache Kafka between .NET and Python agent harness
- **Supervisor Harness:** Python + LangGraph StateGraph
- **Specialist Agents:** Each agent is an independent LangGraph graph with its own Reason → Act → Observe loop
- **Model Gateway:** AWS Bedrock Claude
- **Memory:** MongoDB checkpointer + Qdrant semantic memory + S3 artifact store
- **Tools:** Jira MCP, GitHub MCP, RAG/Qdrant MCP, Custom Document MCP
- **Governance:** Guardrails, Human-in-the-Loop approval, audit logging, observability

## Flagship Use Cases

1. **Requirement & Solution Validation**
   - Helps sales and solution architects validate client requirements against Medidata product features, processes, roadmap, integrations, and compliance posture.

2. **Release Validation & Compliance Impact**
   - Helps existing customers assess product release changes, determine validation needs, prepare evidence packages, and identify potential non-compliance risk.

## Folder Contents

- `prd.md`
- `architecture.md`
- `implementation-roadmap.md`
- `agent-contracts.md`
- `langgraph-workflows.md`
- `mcp-specifications.md`
- `rag-ingestion-pipeline.md`
- `guardrails-hitl.md`
- `observability-audit.md`
- `security-compliance-nfr.md`
- `use-case-01-requirement-solution-validation.md`
- `use-case-02-release-validation-compliance-impact.md`
- `prompts/`
- `schemas/`
- `adrs/`
