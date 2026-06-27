"""Assemble the supervisor LangGraph ``StateGraph``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from medidata_common.config import Settings, get_settings

from supervisor.dispatcher import AgentRunner, LocalStubAgentRunner
from supervisor.guardrails import GuardrailEngine
from supervisor.model_gateway import ModelGateway, create_model_gateway
from supervisor.nodes import SupervisorNodes
from supervisor.state import SupervisorState


@dataclass
class SupervisorDeps:
    model: ModelGateway
    runner: AgentRunner
    guardrails: GuardrailEngine
    audit: Any | None = None


def build_supervisor_graph(deps: SupervisorDeps, checkpointer: Any | None = None):
    """Build and compile the supervisor graph.

    The node chain is linear and mirrors ``docs/langgraph-workflows.md``;
    use-case routing happens inside ``plan_tasks`` and HITL routing inside
    ``human_approval_if_needed``. Tool-failure retry / dead-letter is handled
    at the dispatch and host layers.
    """
    n = SupervisorNodes(
        model=deps.model,
        runner=deps.runner,
        guardrails=deps.guardrails,
        audit=deps.audit,
    )

    g: StateGraph = StateGraph(SupervisorState)
    g.add_node("receive_request", n.receive_request)
    g.add_node("classify_use_case", n.classify_use_case)
    g.add_node("load_context", n.load_context)
    g.add_node("plan_tasks", n.plan_tasks)
    g.add_node("dispatch_agents", n.dispatch_agents)
    g.add_node("collect_results", n.collect_results)
    g.add_node("synthesize_response", n.synthesize_response)
    g.add_node("run_guardrails", n.run_guardrails)
    g.add_node("human_approval_if_needed", n.human_approval_if_needed)
    g.add_node("publish_final_response", n.publish_final_response)

    g.add_edge(START, "receive_request")
    g.add_edge("receive_request", "classify_use_case")
    g.add_edge("classify_use_case", "load_context")
    g.add_edge("load_context", "plan_tasks")
    g.add_edge("plan_tasks", "dispatch_agents")
    g.add_edge("dispatch_agents", "collect_results")
    g.add_edge("collect_results", "synthesize_response")
    g.add_edge("synthesize_response", "run_guardrails")
    g.add_edge("run_guardrails", "human_approval_if_needed")
    g.add_edge("human_approval_if_needed", "publish_final_response")
    g.add_edge("publish_final_response", END)

    return g.compile(checkpointer=checkpointer)


def build_default(
    settings: Settings | None = None,
    runner: AgentRunner | None = None,
    audit: Any | None = None,
    checkpointer: Any | None = None,
):
    """Convenience builder that wires deps from settings.

    Defaults to the offline-friendly stub agent runner; pass a
    :class:`~supervisor.dispatcher.BusAgentRunner` for the distributed path.
    """
    settings = settings or get_settings()
    deps = SupervisorDeps(
        model=create_model_gateway(settings),
        runner=runner or LocalStubAgentRunner(),
        guardrails=GuardrailEngine(settings),
        audit=audit,
    )
    return build_supervisor_graph(deps, checkpointer=checkpointer)
