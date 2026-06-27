# ADR-002: Kafka as .NET/Python Runtime Boundary

## Decision
Use Kafka to connect ASP.NET BFF and Python agent harness.

## Rationale
Kafka enables async processing, streaming status, retry, DLQ handling, and decoupled scaling.

## Consequences
Requires idempotency, message versioning, and operational monitoring.
