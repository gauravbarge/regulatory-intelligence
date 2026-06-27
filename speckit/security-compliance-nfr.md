# Security, Compliance, and Non-Functional Requirements

## Security
- Tenant isolation mandatory
- RBAC for internal vs customer users
- Encryption in transit and at rest
- S3 presigned URLs with expiration
- No cross-customer document retrieval
- Least privilege for MCP tools

## Compliance
- Preserve audit trail for all AI decisions
- Human approval for regulated conclusions
- Version all generated evidence packages
- Retain source citations
- Support inspection-ready export

## Performance
- Simple RAG query: < 10 seconds
- Multi-agent requirement validation: < 5 minutes
- Release validation package generation: < 10 minutes
- Streaming UI updates within 2 seconds of major status changes

## Reliability
- Kafka retries
- Dead letter queue
- Agent-level retry policy
- Idempotent task processing
- Graceful degradation when an agent fails

## Accuracy Requirements
- No compliance conclusion without supporting evidence
- No fabricated document names
- Unsupported requirements must be explicitly marked
- Confidence score must be exposed internally
