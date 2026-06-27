"""Supervisor graph nodes.

Each method is a LangGraph node: ``async (state) -> partial state``. Nodes are
methods of :class:`SupervisorNodes` so they share injected dependencies
(model gateway, agent runner, guardrail engine, audit emitter). The node set
mirrors ``docs/langgraph-workflows.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from medidata_common.audit import AuditAction, AuditEvent
from medidata_common.contracts import (
    AgentDispatch,
    HumanApproval,
    RequestContext,
    SupervisorDecision,
    SupervisorRequest,
    SupervisorResponse,
    UseCase,
)
from medidata_common.logging import get_logger

from supervisor.dispatcher import AgentRunner, agents_for_use_case
from supervisor.guardrails import GuardrailEngine
from supervisor.model_gateway import ModelGateway
from supervisor.state import SupervisorState

log = get_logger("supervisor.nodes")


@dataclass
class SupervisorNodes:
    model: ModelGateway
    runner: AgentRunner
    guardrails: GuardrailEngine
    audit: Any | None = None  # AuditEmitter | None

    async def _emit(self, event: AuditEvent) -> None:
        if self.audit is not None:
            await self.audit.emit(event)

    # 1 ---------------------------------------------------------------- #
    async def receive_request(self, state: SupervisorState) -> dict[str, Any]:
        req = SupervisorRequest.model_validate(state["request"])
        await self._emit(
            AuditEvent(
                request_id=req.request_id,
                user_id=req.user_id,
                tenant_id=req.tenant_id,
                action=AuditAction.USER_REQUEST,
                detail={"use_case": req.use_case.value if req.use_case else None},
            )
        )
        return {
            "request_id": req.request_id,
            "tenant_id": req.tenant_id,
            "user_id": req.user_id,
            "user_query": req.user_query,
            "context": req.context.model_dump(mode="json"),
            "use_case": req.use_case.value if req.use_case else None,
            "agent_results": [],
            "errors": [],
        }

    # 2 ---------------------------------------------------------------- #
    async def classify_use_case(self, state: SupervisorState) -> dict[str, Any]:
        if state.get("use_case"):
            return {"use_case": state["use_case"]}
        ctx = RequestContext.model_validate(state.get("context", {}))
        use_case = await self.model.classify_use_case(state["user_query"], ctx)
        await self._emit(
            AuditEvent(
                request_id=state["request_id"],
                tenant_id=state.get("tenant_id"),
                action=AuditAction.CLASSIFICATION,
                decision=use_case.value,
            )
        )
        return {"use_case": use_case.value}

    # 3 ---------------------------------------------------------------- #
    async def load_context(self, state: SupervisorState) -> dict[str, Any]:
        # Placeholder for semantic-memory recall (Qdrant) and prior-run lookup.
        # The checkpointer already restores thread state; long-term recall will
        # be added with the Research agent / RAG MCP.
        return {}

    # 4 ---------------------------------------------------------------- #
    async def plan_tasks(self, state: SupervisorState) -> dict[str, Any]:
        use_case = state["use_case"] or UseCase.REQUIREMENT_VALIDATION.value
        ctx = RequestContext.model_validate(state.get("context", {}))
        plan: list[dict[str, Any]] = []
        for agent in agents_for_use_case(use_case):
            plan.append(
                AgentDispatch(
                    request_id=state["request_id"],
                    tenant_id=state.get("tenant_id", ""),
                    agent_name=agent,
                    use_case=UseCase(use_case),
                    objective=f"Support '{use_case}' for query: {state['user_query']}",
                    context=ctx,
                ).model_dump(mode="json")
            )
        await self._emit(
            AuditEvent(
                request_id=state["request_id"],
                action=AuditAction.PLAN,
                detail={"agents": [p["agent_name"] for p in plan]},
            )
        )
        return {"plan": plan}

    # 5 ---------------------------------------------------------------- #
    async def dispatch_agents(self, state: SupervisorState) -> dict[str, Any]:
        dispatches = [AgentDispatch.model_validate(p) for p in state.get("plan", [])]
        for d in dispatches:
            await self._emit(
                AuditEvent(
                    request_id=state["request_id"],
                    action=AuditAction.AGENT_DISPATCH,
                    agent_name=d.agent_name.value,
                    detail={"dispatch_id": d.dispatch_id},
                )
            )
        results = await self.runner.run_many(dispatches)
        return {"agent_results": [r.model_dump(mode="json") for r in results]}

    # 6 ---------------------------------------------------------------- #
    async def collect_results(self, state: SupervisorState) -> dict[str, Any]:
        planned = {p["agent_name"] for p in state.get("plan", [])}
        responded = {r["agent_name"] for r in state.get("agent_results", [])}
        missing = planned - responded
        errors = [f"no result from {a}" for a in missing]
        return {"errors": errors}

    # 7 ---------------------------------------------------------------- #
    async def synthesize_response(self, state: SupervisorState) -> dict[str, Any]:
        ctx = RequestContext.model_validate(state.get("context", {}))
        use_case = UseCase(state["use_case"] or UseCase.REQUIREMENT_VALIDATION.value)
        draft = await self.model.synthesize(
            user_query=state["user_query"],
            use_case=use_case,
            agent_results=state.get("agent_results", []),
            context=ctx,
        )
        await self._emit(
            AuditEvent(
                request_id=state["request_id"],
                action=AuditAction.MODEL_OUTPUT,
                decision=draft.get("decision"),
            )
        )
        return {"draft_response": draft}

    # 8 ---------------------------------------------------------------- #
    async def run_guardrails(self, state: SupervisorState) -> dict[str, Any]:
        draft = state.get("draft_response", {})
        confidence = float(draft.get("confidence", 0.0))
        result = self.guardrails.evaluate(draft, confidence)
        await self._emit(
            AuditEvent(
                request_id=state["request_id"],
                action=AuditAction.GUARDRAIL_DECISION,
                decision="human_review" if result.requires_human else "auto_release",
                detail={"reasons": result.reasons, "violations": result.violations},
            )
        )
        return {"guardrail": result.to_dict()}

    # 9 ---------------------------------------------------------------- #
    async def human_approval_if_needed(self, state: SupervisorState) -> dict[str, Any]:
        draft = dict(state.get("draft_response", {}))
        guardrail = state.get("guardrail", {})
        approval = HumanApproval()
        decision = draft.get("decision", SupervisorDecision.SUPPORTED.value)

        if guardrail.get("requires_human"):
            approval = HumanApproval(
                required=True,
                reason="; ".join(guardrail.get("reasons", [])) or "guardrail",
                status="pending",
            )
            decision = SupervisorDecision.HUMAN_REVIEW_REQUIRED.value
            await self._emit(
                AuditEvent(
                    request_id=state["request_id"],
                    action=AuditAction.HUMAN_APPROVAL,
                    approval_status="pending",
                    decision=decision,
                )
            )

        response = SupervisorResponse(
            request_id=state["request_id"],
            decision=SupervisorDecision(decision),
            executive_summary=draft.get("executive_summary", ""),
            evidence_backed_findings=draft.get("evidence_backed_findings", []),
            human_approval=approval,
        )
        return {"final_response": response.model_dump(mode="json")}

    # 10 --------------------------------------------------------------- #
    async def publish_final_response(self, state: SupervisorState) -> dict[str, Any]:
        await self._emit(
            AuditEvent(
                request_id=state["request_id"],
                action=AuditAction.FINAL_RESPONSE,
                decision=state.get("final_response", {}).get("decision"),
                approval_status=state.get("final_response", {})
                .get("human_approval", {})
                .get("status"),
            )
        )
        # Actual Kafka publish to ui.inbound.response is done by the host
        # (app.py) once the graph completes, so the node stays pure/testable.
        return {}
