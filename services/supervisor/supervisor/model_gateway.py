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
        # The structured synthesis prompt lives here in a full build; for now we
        # reuse the deterministic aggregation so behaviour is identical offline
        # and the Bedrock path stays a drop-in. Replace with a JSON-mode call
        # to Claude when wiring real synthesis.
        return await FakeModelGateway().synthesize(
            user_query, use_case, agent_results, context
        )


def create_model_gateway(settings: Settings | None = None) -> ModelGateway:
    settings = settings or get_settings()
    if settings.model_gateway_mode == "bedrock":
        return BedrockModelGateway(settings)
    return FakeModelGateway()
