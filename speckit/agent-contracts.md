# Agent Contracts

All agents must return structured JSON.

## Common Agent Result Schema

```json
{
  "agent_name": "research_agent",
  "task_id": "uuid",
  "status": "success|partial|failed|requires_human_review",
  "confidence": 0.0,
  "summary": "string",
  "findings": [],
  "evidence": [],
  "risks": [],
  "recommended_actions": [],
  "artifacts": [],
  "errors": []
}
```

## Supervisor Input

```json
{
  "request_id": "uuid",
  "user_id": "string",
  "tenant_id": "string",
  "use_case": "requirement_validation|release_validation",
  "user_query": "string",
  "uploaded_artifacts": [],
  "context": {
    "product": "Clinical View",
    "release": "2026.3",
    "client": "optional",
    "study": "optional"
  }
}
```

## Supervisor Output

```json
{
  "request_id": "uuid",
  "decision": "supported|partially_supported|unsupported|validation_required|no_validation_required|human_review_required",
  "executive_summary": "string",
  "evidence_backed_findings": [],
  "gap_analysis": [],
  "compliance_impact": [],
  "validation_recommendations": [],
  "artifacts": [],
  "human_approval": {
    "required": true,
    "reason": "GxP impact"
  }
}
```

## Agent Responsibilities

### Agile Master Agent
- Jira search
- roadmap mapping
- story/defect traceability
- sprint/release status

### Developer Agent
- GitHub repo search
- PR/commit analysis
- API/integration feasibility
- code impact assessment

### Research Agent
- product documentation search
- validation artifact search
- release note search
- SOP/regulatory knowledge retrieval

### Document Analyst Agent
- extract requirements from RFPs
- parse PDFs/Word/Excel files
- classify requirements
- summarize uploaded evidence
