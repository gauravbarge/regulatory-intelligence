"""Model Gateway.

A thin, swappable layer over the LLM. Two implementations:

* :class:`FakeModelGateway` — deterministic, dependency-free. Used for offline
  runs and tests (``MODEL_GATEWAY_MODE=fake``).
* :class:`BedrockModelGateway` — AWS Bedrock Claude via ``langchain-aws``,
  with retries/streaming (``MODEL_GATEWAY_MODE=bedrock``). Imported lazily so
  AWS deps are only required when actually used.

The gateway exposes task-shaped methods (``classify_use_case``,
``synthesize``) rather than a raw ``chat`` call, so prompt construction and
output parsing live in one place and the graph nodes stay clean.
"""

from __future__ import annotations

import abc
from typing import Any

from medidata_common.config import Settings, get_settings
from medidata_common.contracts import (
    AgentStatus,
    Finding,
    RequestContext,
    SupervisorDecision,
    UseCase,
)

# Keyword hints used by the fake gateway and as a cheap prior in prompts.
_RELEASE_HINTS = (
    "release",
    "upgrade",
    "version",
    "patch",
    "hotfix",
    "validation",
    "revalidate",
    "change control",
    "impact",
)


class ModelGateway(abc.ABC):
    """Task-shaped interface over the model."""

    @abc.abstractmethod
    async def classify_use_case(self, user_query: str, context: RequestContext) -> UseCase:
        ...

    @abc.abstractmethod
    async def synthesize(
        self,
        user_query: str,
        use_case: UseCase,
        agent_results: list[dict[str, Any]],
        context: RequestContext,
    ) -> dict[str, Any]:
        """Return a draft SupervisorResponse-shaped dict."""
        ...


class FakeModelGateway(ModelGateway):
    """Deterministic, offline gateway. Good enough to exercise the full graph."""

    async def classify_use_case(
        self, user_query: str, context: RequestContext
    ) -> UseCase:
        q = (user_query or "").lower()
        score = sum(1 for h in _RELEASE_HINTS if h in q)
        # A release/version mentioned in context is a strong signal.
        if context.release:
            score += 1
        return (
            UseCase.RELEASE_VALIDATION
            if score >= 2
            else UseCase.REQUIREMENT_VALIDATION
        )

    async def synthesize(
        self,
        user_query: str,
        use_case: UseCase,
        agent_results: list[dict[str, Any]],
        context: RequestContext,
    ) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        confidences: list[float] = []
        any_failed = False
        any_review = False

        for res in agent_results:
            confidences.append(float(res.get("confidence", 0.0)))
            status = res.get("status")
            if status == AgentStatus.FAILED.value:
                any_failed = True
            if status == AgentStatus.REQUIRES_HUMAN_REVIEW.value:
                any_review = True
            for f in res.get("findings", []):
                findings.append(
                    Finding(
                        statement=f.get("statement", ""),
                        confidence=float(f.get("confidence", 0.0)),
                        evidence_ids=f.get("evidence_ids", []),
                    ).model_dump(mode="json")
                )

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        decision = self._decide(use_case, avg_conf, any_failed, any_review)

        summary = (
            f"Synthesized {len(agent_results)} agent result(s) for "
            f"'{use_case.value}'. Mean agent confidence {avg_conf:.2f}. "
            f"{len(findings)} finding(s) collected."
        )
        return {
            "decision": decision.value,
            "executive_summary": summary,
            "evidence_backed_findings": findings,
            "confidence": avg_conf,
        }

    @staticmethod
    def _decide(
        use_case: UseCase, avg_conf: float, any_failed: bool, any_review: bool
    ) -> SupervisorDecision:
        if any_review:
            return SupervisorDecision.HUMAN_REVIEW_REQUIRED
        if use_case is UseCase.RELEASE_VALIDATION:
            if any_failed or avg_conf < 0.5:
                return SupervisorDecision.VALIDATION_REQUIRED
            return SupervisorDecision.NO_VALIDATION_REQUIRED
        # requirement validation
        if avg_conf >= 0.75:
            return SupervisorDecision.SUPPORTED
        if avg_conf >= 0.4:
            return SupervisorDecision.PARTIALLY_SUPPORTED
        return SupervisorDecision.UNSUPPORTED


class BedrockModelGateway(ModelGateway):
    """AWS Bedrock Claude gateway (lazy import of langchain-aws)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm: Any = None

    def _client(self) -> Any:
        if self._llm is None:
            from langchain_aws import ChatBedrockConverse  # lazy

            self._llm = ChatBedrockConverse(
                model=self._settings.bedrock_model_id,
                region_name=self._settings.aws_region,
                max_tokens=self._settings.bedrock_max_tokens,
                temperature=self._settings.bedrock_temperature,
            )
        return self._llm

    async def classify_use_case(
        self, user_query: str, context: RequestContext
    ) -> UseCase:
        from langchain_core.messages import HumanMessage, SystemMessage

        sys = SystemMessage(
            content=(
                "Classify the request as exactly one of: "
                "requirement_validation, release_validation. "
                "Answer with only the label."
            )
        )
        human = HumanMessage(content=f"Context: {context.model_dump()}\n\n{user_query}")
        resp = await self._client().ainvoke([sys, human])
        label = str(resp.content).strip().lower()
        try:
            return UseCase(label)
        except ValueError:
            # Fall back to the deterministic heuristic on an unexpected label.
            return await FakeModelGateway().classify_use_case(user_query, context)

    async def synthesize(
        self,
        user_query: str,
        use_case: UseCase,
        agent_results: list[dict[str, Any]],
        context: RequestContext,
    ) -> dict[str, Any]:
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        # Build a compact summary of agent results to keep token count manageable.
        agent_summaries = []
        for r in agent_results:
            agent_summaries.append({
                "agent": r.get("agent_name"),
                "status": r.get("status"),
                "confidence": r.get("confidence"),
                "summary": r.get("summary", ""),
                "findings": [f.get("statement") for f in r.get("findings", [])[:3]],
                "evidence_count": len(r.get("evidence", [])),
            })

        decision_options = (
            "supported, partially_supported, unsupported, "
            "validation_required, no_validation_required, human_review_required"
        )
        sys_msg = SystemMessage(
            content=(
                "You are the Regulatory Intelligence Supervisor. Synthesize the agent results "
                "into a structured response. Reply ONLY with valid JSON matching this schema:\n"
                '{"decision": "<one of: ' + decision_options + '>", '
                '"executive_summary": "<2-3 sentence summary>", '
                '"evidence_backed_findings": [{"statement": "...", "confidence": 0.0, "evidence_ids": []}], '
                '"confidence": 0.0}\n'
                "Rules: Never make compliance claims without evidence. "
                "Mark human_review_required if any finding lacks evidence or confidence < 0.7."
            )
        )
        human_msg = HumanMessage(
            content=(
                f"Use case: {use_case.value}\n"
                f"User query: {user_query}\n"
                f"Context: {context.model_dump()}\n\n"
                f"Agent results:\n{json.dumps(agent_summaries, indent=2)}"
            )
        )
        try:
            resp = await self._client().ainvoke([sys_msg, human_msg])
            raw = str(resp.content).strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            # Validate required keys are present
            if "decision" in parsed and "executive_summary" in parsed:
                return parsed
        except Exception:
            pass
        # Fall back to deterministic aggregation on any parse/network failure.
        return await FakeModelGateway().synthesize(user_query, use_case, agent_results, context)


def create_model_gateway(settings: Settings | None = None) -> ModelGateway:
    settings = settings or get_settings()
    if settings.model_gateway_mode == "bedrock":
        return BedrockModelGateway(settings)
    return FakeModelGateway()
