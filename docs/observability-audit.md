# Observability and Audit

## Observability Stack
- LangSmith for LangGraph traces
- OpenTelemetry for distributed tracing
- Kafka message tracking
- MongoDB execution records
- S3 artifact history

## Audit Events
Capture:
- user request
- classification
- plan
- agent dispatch
- tool calls
- retrieved evidence
- model outputs
- guardrail decisions
- human approvals
- final response

## Required Audit Fields
- request_id
- user_id
- tenant_id
- timestamp
- action
- agent_name
- tool_name
- evidence_ids
- decision
- approval_status

## Dashboards
- average task latency
- agent failure rate
- DLQ count
- HITL approval volume
- top customer requirement gaps
- release validation request volume
