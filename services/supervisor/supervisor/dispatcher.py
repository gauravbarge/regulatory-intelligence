"""Agent dispatch.

The supervisor does not run specialist logic itself — it dispatches a sub-task
to an independent agent graph and awaits a structured :class:`AgentResult`.
This module defines the seam:

* :class:`AgentRunner` — protocol the supervisor depends on.
* :class:`LocalStubAgentRunner` — returns deterministic placeholder results so
  the supervisor is testable before the real agents exist (and for offline
  runs).
* :class:`BusAgentRunner` — the production path: publishes ``AgentDispatch`` to
  the ``agent.dispatch`` topic and correlates the matching ``AgentResult`` from
  ``agent.result`` by ``dispatch_id``.
"""

from __future__ import annotations

import abc
import asyncio

from medidata_common.contracts import (
    AgentDispatch,
    AgentName,
    AgentResult,
    AgentStatus,
    Evidence,
    Finding,
)
from medidata_common.messaging.base import MessageBus
from medidata_common.topics import Topics


class AgentRunner(abc.ABC):
    @abc.abstractmethod
    async def run(self, dispatch: AgentDispatch) -> AgentResult:
        ...

    async def run_many(self, dispatches: list[AgentDispatch]) -> list[AgentResult]:
        """Run dispatches concurrently."""
        return list(await asyncio.gather(*(self.run(d) for d in dispatches)))


class LocalStubAgentRunner(AgentRunner):
    """Deterministic stand-in for real agent graphs.

    Produces a plausible, evidence-backed result so the supervisor graph,
    guardrails and synthesis can be exercised end-to-end without the agents.
    """

    def __init__(self, confidence: float = 0.85) -> None:
        self._confidence = confidence

    async def run(self, dispatch: AgentDispatch) -> AgentResult:
        agent = dispatch.agent_name
        ev = Evidence(
            source=f"stub:{agent.value}",
            artifact_type="stub",
            title=f"{agent.value} evidence",
            snippet=f"Stub evidence for objective: {dispatch.objective[:60]}",
            score=self._confidence,
        )
        finding = Finding(
            statement=f"{agent.value} addressed: {dispatch.objective[:80]}",
            confidence=self._confidence,
            evidence_ids=[ev.evidence_id],
        )
        return AgentResult(
            agent_name=agent,
            task_id=dispatch.dispatch_id,
            request_id=dispatch.request_id,
            status=AgentStatus.SUCCESS,
            confidence=self._confidence,
            summary=f"{agent.value} completed sub-task.",
            findings=[finding],
            evidence=[ev],
        )


class BusAgentRunner(AgentRunner):
    """Dispatches over the message bus and awaits correlated results.

    A background consumer task reads ``agent.result`` and resolves the future
    registered for each ``dispatch_id``.
    """

    def __init__(self, bus: MessageBus, timeout_s: float = 60.0) -> None:
        self._bus = bus
        self._timeout = timeout_s
        self._pending: dict[str, asyncio.Future[AgentResult]] = {}
        self._consumer_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._consumer_task = asyncio.create_task(self._consume_results())

    async def stop(self) -> None:
        if self._consumer_task:
            self._consumer_task.cancel()
            self._consumer_task = None

    async def _consume_results(self) -> None:
        async for msg in self._bus.consume([str(Topics.AGENT_RESULT)]):
            dispatch_id = msg.value.get("task_id")
            fut = self._pending.pop(dispatch_id, None)
            if fut and not fut.done():
                fut.set_result(AgentResult.model_validate(msg.value))

    async def run(self, dispatch: AgentDispatch) -> AgentResult:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[AgentResult] = loop.create_future()
        self._pending[dispatch.dispatch_id] = fut
        await self._bus.produce(
            topic=str(Topics.AGENT_DISPATCH),
            value=dispatch.model_dump(mode="json"),
            key=dispatch.request_id,
        )
        try:
            return await asyncio.wait_for(fut, timeout=self._timeout)
        except asyncio.TimeoutError:
            self._pending.pop(dispatch.dispatch_id, None)
            return AgentResult(
                agent_name=dispatch.agent_name,
                task_id=dispatch.dispatch_id,
                request_id=dispatch.request_id,
                status=AgentStatus.FAILED,
                confidence=0.0,
                summary="Agent did not respond within timeout.",
                errors=[f"timeout after {self._timeout}s"],
            )


# Default agent assignment per use case (docs/langgraph-workflows.md).
def agents_for_use_case(use_case_value: str) -> list[AgentName]:
    from medidata_common.contracts import UseCase

    if use_case_value == UseCase.RELEASE_VALIDATION.value:
        return [
            AgentName.RESEARCH,
            AgentName.DEVELOPER,
            AgentName.AGILE_MASTER,
            AgentName.DOCUMENT_ANALYST,
        ]
    return [
        AgentName.DOCUMENT_ANALYST,
        AgentName.RESEARCH,
        AgentName.AGILE_MASTER,
        AgentName.DEVELOPER,
    ]
