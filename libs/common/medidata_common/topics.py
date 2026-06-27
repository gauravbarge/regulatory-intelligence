"""Kafka topic names — the runtime boundary between the .NET BFF and the
Python agent tier. Mirrors `docs/architecture.md`.
"""

from __future__ import annotations

from enum import Enum


class Topics(str, Enum):
    """Canonical Kafka topic names."""

    TASK_REQUEST = "task.request"
    AGENT_DISPATCH = "agent.dispatch"
    AGENT_RESULT = "agent.result"
    UI_INBOUND_RESPONSE = "ui.inbound.response"
    TOOL_CALL_EVENT = "tool.call.event"
    DEAD_LETTER = "dead.letter"
    AUDIT_EVENT = "audit.event"

    def __str__(self) -> str:  # so it serializes as the plain topic name
        return self.value


ALL_TOPICS: tuple[str, ...] = tuple(t.value for t in Topics)
