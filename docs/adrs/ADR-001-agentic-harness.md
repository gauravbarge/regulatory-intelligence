# ADR-001: Each Agent as Independent LangGraph Graph

## Decision
Each specialist agent will be implemented as its own LangGraph graph rather than as a simple tool.

## Rationale
This gives each agent independent reasoning, tool retries, state, observability, and memory recall.

## Consequences
Supervisor complexity decreases, but agent contract discipline becomes critical.
