"""Research agent smoke tests (offline, no external services)."""

import pytest
from medidata_common.contracts import AgentName, AgentStatus, UseCase
from medidata_common.messaging.memory import InMemoryBus
from medidata_common.topics import Topics

from research_agent.graph import build_research_graph
from research_agent.tools import StubRagTool, StubKnowledgeBaseTool


@pytest.fixture
def graph():
    return build_research_graph(tools=[StubRagTool(), StubKnowledgeBaseTool()])


def _make_dispatch(objective: str = "Does Clinical View support audit trails?") -> dict:
    from medidata_common.contracts import AgentDispatch, RequestContext, UseCase
    d = AgentDispatch(
        request_id="req-001",
        tenant_id="tenant-test",
        agent_name=AgentName.RESEARCH,
        use_case=UseCase.REQUIREMENT_VALIDATION,
        objective=objective,
        context=RequestContext(product="Clinical View", release="2026.3"),
    )
    return d.model_dump(mode="json")


@pytest.mark.asyncio
async def test_research_agent_produces_result(graph):
    dispatch = _make_dispatch()
    final = await graph.ainvoke(
        {"dispatch": dispatch},
        config={"configurable": {"thread_id": "t1"}},
    )
    result = final["result"]
    assert result["agent_name"] == AgentName.RESEARCH.value
    assert result["request_id"] == "req-001"
    assert result["status"] in (AgentStatus.SUCCESS.value, AgentStatus.PARTIAL.value)
    assert len(result["findings"]) >= 1
    assert len(result["evidence"]) >= 1


@pytest.mark.asyncio
async def test_research_agent_evidence_has_ids(graph):
    dispatch = _make_dispatch("Retrieve validation evidence for 21 CFR Part 11")
    final = await graph.ainvoke(
        {"dispatch": dispatch},
        config={"configurable": {"thread_id": "t2"}},
    )
    result = final["result"]
    for finding in result["findings"]:
        # Every finding must carry evidence_ids when evidence is present
        if result["evidence"]:
            assert finding["evidence_ids"], "finding missing evidence_ids"


@pytest.mark.asyncio
async def test_bus_round_trip():
    """Full dispatch → agent.result round-trip via InMemoryBus."""
    import asyncio
    from medidata_common.agent_harness import run_agent_app

    bus = InMemoryBus()
    await bus.start()
    graph = build_research_graph(tools=[StubRagTool(), StubKnowledgeBaseTool()])

    dispatch = _make_dispatch()

    async def _run():
        await run_agent_app(AgentName.RESEARCH, graph, bus, "test-group")

    task = asyncio.create_task(_run())

    await bus.produce(
        topic=str(Topics.AGENT_DISPATCH),
        value=dispatch,
        key=dispatch["request_id"],
    )

    msg = await bus.get_one(str(Topics.AGENT_RESULT), timeout=5.0)
    task.cancel()

    assert msg.value["agent_name"] == AgentName.RESEARCH.value
    assert msg.value["request_id"] == "req-001"
