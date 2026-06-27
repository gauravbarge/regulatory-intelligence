"""Audit event model and emitter.

Every significant action (classification, plan, dispatch, tool call, guardrail
decision, approval, final response) is captured as an :class:`AuditEvent` and
published to the ``audit.event`` Kafka topic. Required fields follow
``docs/observability-audit.md``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from medidata_common.topics import Topics


class AuditAction(str, Enum):
    USER_REQUEST = "user_request"
    CLASSIFICATION = "classification"
    PLAN = "plan"
    AGENT_DISPATCH = "agent_dispatch"
    TOOL_CALL = "tool_call"
    EVIDENCE_RETRIEVED = "evidence_retrieved"
    MODEL_OUTPUT = "model_output"
    GUARDRAIL_DECISION = "guardrail_decision"
    HUMAN_APPROVAL = "human_approval"
    FINAL_RESPONSE = "final_response"
    ERROR = "error"


class AuditEvent(BaseModel):
    """A single immutable audit record."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    user_id: str | None = None
    tenant_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: AuditAction
    agent_name: str | None = None
    tool_name: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    decision: str | None = None
    approval_status: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditEmitter:
    """Publishes audit events to the audit topic via a message bus.

    The bus is anything with an async ``produce(topic, key, value)`` method
    (see :mod:`medidata_common.messaging`).
    """

    def __init__(self, bus: Any) -> None:
        self._bus = bus

    async def emit(self, event: AuditEvent) -> None:
        await self._bus.produce(
            topic=str(Topics.AUDIT_EVENT),
            key=event.request_id,
            value=event.model_dump(mode="json"),
        )
