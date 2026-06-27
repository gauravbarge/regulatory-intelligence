"""Agile Master agent smoke tests."""

import pytest
from medidata_common.contracts import AgentName, AgentStatus, UseCase

from agile_master_agent.graph import build_agile_graph
from agile_master_agent.tools import StubJiraSearchTool, StubRoadmapTool


@pytest.fixture
def graph():
    return build_agile_graph(tools=[StubJiraSearchTool(), StubRoadmapTool()])


def _make_dispatch(objective: str = "Find Jira stories for e-signature feature") -> dict:
    from medidata_common.contracts import AgentDispatch, RequestContext
    d = AgentDispatch(
        request_id="req-agile-001",
        tenant_id="tenant-test",
        agent_name=AgentName.AGILE_MASTER,
        use_case=UseCase.REQUIREMENT_VALIDATION,
        objective=objective,
        context=RequestContext(product="Clinical View", release="2026.3"),
    )
    return d.model_dump(mode="json")


@pytest.mark.asyncio
async def test_agile_agent_produces_result(graph):
    dispatch = _make_dispatch()
    final = await graph.ainvoke(
        {"dispatch": dispatch},
        config={"configurable": {"thread_id": "agile-t1"}},
    )
    result = final["result"]
    assert result["agent_name"] == AgentName.AGILE_MASTER.value
    assert result["status"] in (AgentStatus.SUCCESS.value, AgentStatus.PARTIAL.value)
    assert result["confidence"] > 0


@pytest.mark.asyncio
async def test_agile_agent_roadmap_lookup(graph):
    dispatch = _make_dispatch("What is on the roadmap for custom dashboards?")
    final = await graph.ainvoke(
        {"dispatch": dispatch},
        config={"configurable": {"thread_id": "agile-t2"}},
    )
    assert len(final["result"]["evidence"]) >= 1
