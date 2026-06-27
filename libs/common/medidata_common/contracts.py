"""Cross-service data contracts.

These pydantic models are the typed, validated form of the JSON contracts in
``docs/agent-contracts.md`` and ``docs/schemas/``. They are shared by the
supervisor and every specialist agent so the Kafka payloads are consistent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid4())


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class UseCase(str, Enum):
    REQUIREMENT_VALIDATION = "requirement_validation"
    RELEASE_VALIDATION = "release_validation"


class AgentName(str, Enum):
    AGILE_MASTER = "agile_master_agent"
    DEVELOPER = "developer_agent"
    RESEARCH = "research_agent"
    DOCUMENT_ANALYST = "document_analyst_agent"


class AgentStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class SupervisorDecision(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    VALIDATION_REQUIRED = "validation_required"
    NO_VALIDATION_REQUIRED = "no_validation_required"
    HUMAN_REVIEW_REQUIRED = "human_review_required"


class RequirementStatus(str, Enum):
    SUPPORTED = "Supported"
    CONFIGURABLE = "Configurable"
    CUSTOM_REQUIRED = "Custom Required"
    ROADMAP = "Roadmap"
    UNSUPPORTED = "Unsupported"
    UNKNOWN = "Unknown"


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #
class Evidence(BaseModel):
    """A single cited piece of supporting evidence."""

    evidence_id: str = Field(default_factory=_new_id)
    source: str = ""  # e.g. "qdrant:validation_summary", "jira:MDV-1234"
    artifact_type: str | None = None
    title: str | None = None
    snippet: str | None = None
    uri: str | None = None
    score: float | None = None


class Finding(BaseModel):
    statement: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class Risk(BaseModel):
    description: str
    severity: str = "medium"  # low|medium|high|critical
    likelihood: str | None = None
    mitigation: str | None = None


class RecommendedAction(BaseModel):
    action: str
    rationale: str | None = None
    priority: str = "medium"


class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=_new_id)
    name: str
    artifact_type: str  # report|evidence_package|coverage_matrix|...
    s3_uri: str | None = None
    content_type: str | None = None


class Requirement(BaseModel):
    """Mirrors ``docs/schemas/requirement.schema.json``."""

    requirement_id: str
    requirement_text: str
    category: str | None = None
    status: RequirementStatus = RequirementStatus.UNKNOWN
    evidence: list[Evidence] = Field(default_factory=list)
    risk: str | None = None


# --------------------------------------------------------------------------- #
# Supervisor input / output (docs/agent-contracts.md)
# --------------------------------------------------------------------------- #
class RequestContext(BaseModel):
    product: str | None = None
    release: str | None = None
    client: str | None = None
    study: str | None = None


class SupervisorRequest(BaseModel):
    request_id: str = Field(default_factory=_new_id)
    user_id: str
    tenant_id: str
    use_case: UseCase | None = None  # may be None -> classified by supervisor
    user_query: str
    uploaded_artifacts: list[str] = Field(default_factory=list)  # s3 uris
    context: RequestContext = Field(default_factory=RequestContext)
    created_at: datetime = Field(default_factory=_utcnow)


class HumanApproval(BaseModel):
    required: bool = False
    reason: str | None = None
    status: str = "not_required"  # not_required|pending|approved|edited|rejected
    reviewer: str | None = None
    decided_at: datetime | None = None


class SupervisorResponse(BaseModel):
    request_id: str
    decision: SupervisorDecision
    executive_summary: str = ""
    evidence_backed_findings: list[Finding] = Field(default_factory=list)
    gap_analysis: list[dict[str, Any]] = Field(default_factory=list)
    compliance_impact: list[dict[str, Any]] = Field(default_factory=list)
    validation_recommendations: list[RecommendedAction] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    human_approval: HumanApproval = Field(default_factory=HumanApproval)
    created_at: datetime = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Agent dispatch / result (the supervisor <-> agent contract)
# --------------------------------------------------------------------------- #
class AgentDispatch(BaseModel):
    """A sub-task the supervisor sends to one specialist agent graph."""

    dispatch_id: str = Field(default_factory=_new_id)
    request_id: str
    tenant_id: str
    agent_name: AgentName
    use_case: UseCase
    objective: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    context: RequestContext = Field(default_factory=RequestContext)
    created_at: datetime = Field(default_factory=_utcnow)


class AgentResult(BaseModel):
    """Common agent result schema (docs/agent-contracts.md)."""

    model_config = ConfigDict(use_enum_values=False)

    agent_name: AgentName
    task_id: str  # == dispatch_id
    request_id: str
    status: AgentStatus = AgentStatus.SUCCESS
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)


class DeadLetter(BaseModel):
    """Payload written to the ``dead.letter`` topic after retries are exhausted."""

    request_id: str
    agent_name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    retry_count: int = 0
    timestamp: datetime = Field(default_factory=_utcnow)
