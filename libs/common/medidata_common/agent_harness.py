"""Shared agent harness.

Provides the base ReAct-loop graph builder and bus-driven app runner that
every specialist agent service reuses. Each agent supplies its own set of
:class:`AgentTool` implementations; everything else (state schema, 7-node
graph, Kafka consume/publish lifecycle) is handled here.

Node sequence (langgraph-workflows.md):
    receive_subtask -> recall_memory -> reason -> act_tool_call
    -> observe_result -> decide_continue_or_finish
         |-> (continue) reason
         |-> (done)     produce_structured_result -> END
"""

from __future__ import annotations

import abc
import asyncio
import operator
from dataclasses import dataclass, field
from typing import Annotated, Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from medidata_common.audit import AuditAction, AuditEmitter, AuditEvent
from medidata_common.contracts import (
    AgentDispatch,
    AgentName,
    AgentResult,
    AgentStatus,
    Evidence,
    Finding,
    RecommendedAction,
    Risk,
)
from medidata_common.logging import get_logger
from medidata_common.messaging.base import MessageBus
from medidata_common.topics import Topics

_MAX_ITERATIONS = 6
_log = get_logger("agent_harness")


# ---------------------------------------------------------------------------
# Tool contract
# ---------------------------------------------------------------------------

class AgentTool(abc.ABC):
    """A tool the ReAct loop can invoke. Implement one per external capability."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def description(self) -> str: ...

    @abc.abstractmethod
    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool and return a result dict."""
        ...


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    # Input
    dispatch: dict[str, Any]
    dispatch_id: str
    request_id: str
    tenant_id: str
    agent_name: str
    use_case: str
    objective: str
    context: dict[str, Any]

    # ReAct loop
    iteration: int
    tool_calls: Annotated[list[dict[str, Any]], operator.add]
    observations: Annotated[list[dict[str, Any]], operator.add]
    done: bool

    # Output
    result: dict[str, Any]
    errors: Annotated[list[str], operator.add]


# ---------------------------------------------------------------------------
# Harness nodes
# ---------------------------------------------------------------------------

@dataclass
class AgentHarnessNodes:
    agent_name: AgentName
    tools: list[AgentTool]
    model: Any  # LangChain chat model (or None for stub)
    audit: AuditEmitter | None = None
    max_iterations: int = _MAX_ITERATIONS
    _tool_map: dict[str, AgentTool] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._tool_map = {t.name: t for t in self.tools}

    async def _emit(self, event: AuditEvent) -> None:
        if self.audit is not None:
            await self.audit.emit(event)

    # 1 ------------------------------------------------------------------- #
    async def receive_subtask(self, state: AgentState) -> dict[str, Any]:
        d = AgentDispatch.model_validate(state["dispatch"])
        return {
            "dispatch_id": d.dispatch_id,
            "request_id": d.request_id,
            "tenant_id": d.tenant_id,
            "agent_name": d.agent_name.value,
            "use_case": d.use_case.value,
            "objective": d.objective,
            "context": d.context.model_dump(mode="json"),
            "iteration": 0,
            "tool_calls": [],
            "observations": [],
            "done": False,
            "errors": [],
        }

    # 2 ------------------------------------------------------------------- #
    async def recall_memory(self, state: AgentState) -> dict[str, Any]:
        # Lightweight — placeholder for Qdrant semantic memory recall.
        # Returns nothing; checkpointer thread state already carries prior runs.
        return {}

    # 3 ------------------------------------------------------------------- #
    async def reason(self, state: AgentState) -> dict[str, Any]:
        """Choose the next tool call via LLM or heuristic fallback."""
        iteration = state.get("iteration", 0)
        observations = state.get("observations", [])
        objective = state.get("objective", "")

        if self.model is not None:
            tool_call = await self._llm_reason(objective, observations, iteration)
        else:
            tool_call = self._heuristic_reason(objective, observations, iteration)

        return {"tool_calls": [tool_call], "iteration": iteration + 1}

    async def _llm_reason(
        self,
        objective: str,
        observations: list[dict[str, Any]],
        iteration: int,
    ) -> dict[str, Any]:
        from langchain_core.messages import HumanMessage, SystemMessage

        tool_list = "\n".join(
            f"- {t.name}: {t.description}" for t in self.tools
        )
        obs_text = "\n".join(
            f"Observation {i+1}: {o.get('result', '')}"
            for i, o in enumerate(observations)
        )
        sys_msg = SystemMessage(
            content=(
                f"You are {self.agent_name.value}. Choose the best tool to make "
                "progress on the objective. Reply with JSON: "
                '{"tool": "<name>", "inputs": {<key: value>}}. '
                f"Available tools:\n{tool_list}"
            )
        )
        human_msg = HumanMessage(
            content=(
                f"Objective: {objective}\n\n"
                f"Prior observations:\n{obs_text or 'None yet'}\n\n"
                f"Iteration {iteration + 1}/{self.max_iterations}. Pick a tool."
            )
        )
        try:
            import json
            resp = await self.model.ainvoke([sys_msg, human_msg])
            raw = str(resp.content).strip()
            # Strip markdown code fence if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            if parsed.get("tool") in self._tool_map:
                return {"tool": parsed["tool"], "inputs": parsed.get("inputs", {})}
        except Exception:
            pass
        return self._heuristic_reason(objective, [], iteration)

    def _heuristic_reason(
        self,
        objective: str,
        observations: list[dict[str, Any]],
        iteration: int,
    ) -> dict[str, Any]:
        """Pick the next tool in rotation when no LLM is available."""
        idx = iteration % len(self.tools)
        tool = self.tools[idx]
        return {"tool": tool.name, "inputs": {"query": objective}}

    # 4 ------------------------------------------------------------------- #
    async def act_tool_call(self, state: AgentState) -> dict[str, Any]:
        calls = state.get("tool_calls", [])
        if not calls:
            return {}
        call = calls[-1]
        tool_name = call.get("tool", "")
        inputs = call.get("inputs", {})
        tool = self._tool_map.get(tool_name)
        if tool is None:
            return {"observations": [{"tool": tool_name, "result": f"unknown tool: {tool_name}", "error": True}]}

        await self._emit(
            AuditEvent(
                request_id=state.get("request_id", ""),
                tenant_id=state.get("tenant_id"),
                action=AuditAction.TOOL_CALL,
                agent_name=state.get("agent_name"),
                tool_name=tool_name,
            )
        )
        try:
            result = await tool.call(inputs)
            return {"observations": [{"tool": tool_name, "inputs": inputs, "result": result, "error": False}]}
        except Exception as exc:
            _log.warning("tool.error", tool=tool_name, error=str(exc))
            return {"observations": [{"tool": tool_name, "inputs": inputs, "result": str(exc), "error": True}]}

    # 5 ------------------------------------------------------------------- #
    async def observe_result(self, state: AgentState) -> dict[str, Any]:
        observations = state.get("observations", [])
        if observations:
            last = observations[-1]
            await self._emit(
                AuditEvent(
                    request_id=state.get("request_id", ""),
                    action=AuditAction.EVIDENCE_RETRIEVED,
                    agent_name=state.get("agent_name"),
                    tool_name=last.get("tool"),
                )
            )
        return {}

    # 6 ------------------------------------------------------------------- #
    async def decide_continue_or_finish(self, state: AgentState) -> dict[str, Any]:
        iteration = state.get("iteration", 0)
        observations = state.get("observations", [])
        successful = [o for o in observations if not o.get("error")]

        done = (
            iteration >= self.max_iterations
            or (len(successful) >= min(2, len(self.tools)))
        )
        return {"done": done}

    # 7 ------------------------------------------------------------------- #
    async def produce_structured_result(self, state: AgentState) -> dict[str, Any]:
        observations = state.get("observations", [])
        successful = [o for o in observations if not o.get("error")]
        errors = [o for o in observations if o.get("error")]

        evidence_list: list[Evidence] = []
        findings: list[Finding] = []

        for obs in successful:
            tool_result = obs.get("result", {})
            if isinstance(tool_result, dict):
                items = tool_result.get("hits", tool_result.get("results", tool_result.get("items", [])))
                if isinstance(items, list):
                    for item in items[:5]:
                        ev = Evidence(
                            source=f"{obs['tool']}:{item.get('id', item.get('key', 'unknown'))}",
                            artifact_type=obs.get("tool"),
                            title=item.get("title", item.get("summary", item.get("name", ""))),
                            snippet=item.get("snippet", item.get("body", item.get("description", ""))[:200] if item.get("body") or item.get("description") else ""),
                            score=float(item.get("score", 0.85)),
                        )
                        evidence_list.append(ev)
                elif isinstance(tool_result, dict) and tool_result.get("content"):
                    ev = Evidence(
                        source=f"{obs['tool']}:result",
                        artifact_type=obs.get("tool"),
                        snippet=str(tool_result.get("content", ""))[:300],
                        score=0.8,
                    )
                    evidence_list.append(ev)

        if evidence_list:
            findings.append(
                Finding(
                    statement=f"{self.agent_name.value} found {len(evidence_list)} relevant evidence item(s) for: {state.get('objective', '')[:80]}",
                    confidence=min(0.5 + 0.1 * len(evidence_list), 0.95),
                    evidence_ids=[e.evidence_id for e in evidence_list],
                )
            )
        else:
            findings.append(
                Finding(
                    statement=f"{self.agent_name.value}: no evidence found for objective",
                    confidence=0.2,
                    evidence_ids=[],
                )
            )

        status = AgentStatus.SUCCESS if evidence_list else AgentStatus.PARTIAL
        if errors and not evidence_list:
            status = AgentStatus.FAILED

        confidence = findings[0].confidence if findings else 0.2
        result = AgentResult(
            agent_name=self.agent_name,
            task_id=state.get("dispatch_id", ""),
            request_id=state.get("request_id", ""),
            status=status,
            confidence=confidence,
            summary=(
                f"{self.agent_name.value} completed {len(successful)}/{len(observations)} tool calls. "
                f"Found {len(evidence_list)} evidence item(s)."
            ),
            findings=findings,
            evidence=evidence_list,
            errors=[str(e.get("result")) for e in errors],
        )

        await self._emit(
            AuditEvent(
                request_id=state.get("request_id", ""),
                action=AuditAction.FINAL_RESPONSE,
                agent_name=self.agent_name.value,
                evidence_ids=[e.evidence_id for e in evidence_list],
                decision=status.value,
            )
        )

        return {"result": result.model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _route_after_decide(state: AgentState) -> str:
    return "produce_structured_result" if state.get("done") else "reason"


def build_agent_graph(
    agent_name: AgentName,
    tools: list[AgentTool],
    model: Any = None,
    audit: AuditEmitter | None = None,
    checkpointer: Any = None,
    max_iterations: int = _MAX_ITERATIONS,
):
    """Build and compile a specialist agent graph."""
    n = AgentHarnessNodes(
        agent_name=agent_name,
        tools=tools,
        model=model,
        audit=audit,
        max_iterations=max_iterations,
    )

    g: StateGraph = StateGraph(AgentState)
    g.add_node("receive_subtask", n.receive_subtask)
    g.add_node("recall_memory", n.recall_memory)
    g.add_node("reason", n.reason)
    g.add_node("act_tool_call", n.act_tool_call)
    g.add_node("observe_result", n.observe_result)
    g.add_node("decide_continue_or_finish", n.decide_continue_or_finish)
    g.add_node("produce_structured_result", n.produce_structured_result)

    g.add_edge(START, "receive_subtask")
    g.add_edge("receive_subtask", "recall_memory")
    g.add_edge("recall_memory", "reason")
    g.add_edge("reason", "act_tool_call")
    g.add_edge("act_tool_call", "observe_result")
    g.add_edge("observe_result", "decide_continue_or_finish")
    g.add_conditional_edges("decide_continue_or_finish", _route_after_decide)
    g.add_edge("produce_structured_result", END)

    return g.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Bus-driven app runner
# ---------------------------------------------------------------------------

async def run_agent_app(
    agent_name: AgentName,
    graph: Any,
    bus: MessageBus,
    consumer_group: str = "agents",
) -> None:
    """Consume agent.dispatch, run the graph, publish agent.result."""
    _log.info("agent.starting", agent=agent_name.value)
    async for msg in bus.consume([str(Topics.AGENT_DISPATCH)], group=consumer_group):
        value = msg.value
        if value.get("agent_name") != agent_name.value:
            continue
        dispatch_id = value.get("dispatch_id", "unknown")
        request_id = value.get("request_id", "unknown")
        _log.info("agent.dispatch.received", agent=agent_name.value, dispatch_id=dispatch_id)
        try:
            config = {"configurable": {"thread_id": dispatch_id}}
            final_state = await graph.ainvoke({"dispatch": value}, config=config)
            result = final_state.get("result", {})
        except Exception as exc:
            _log.error("agent.error", agent=agent_name.value, error=str(exc))
            result = AgentResult(
                agent_name=agent_name,
                task_id=dispatch_id,
                request_id=request_id,
                status=AgentStatus.FAILED,
                confidence=0.0,
                summary=f"Unhandled error: {exc}",
                errors=[str(exc)],
            ).model_dump(mode="json")

        await bus.produce(
            topic=str(Topics.AGENT_RESULT),
            value=result,
            key=request_id,
        )
        _log.info("agent.result.published", agent=agent_name.value, dispatch_id=dispatch_id)
