"""Developer agent smoke tests."""

import pytest
from medidata_common.contracts import AgentName, AgentStatus, UseCase

from developer_agent.graph import build_developer_graph
from developer_agent.tools import StubGitHubSearchTool, StubCommitAnalysisTool


@pytest.fixture
def graph():
    return build_developer_graph(tools=[StubGitHubSearchTool(), StubCommitAnalysisTool()])


def _make_dispatch(objective: str = "Analyze changed APIs in release 2026.3") -> dict:
    from medidata_common.contracts import AgentDispatch, RequestContext
    d = AgentDispatch(
        request_id="req-dev-001",
        tenant_id="tenant-test",
        agent_name=AgentName.DEVELOPER,
        use_case=UseCase.RELEASE_VALIDATION,
        objective=objective,
        context=RequestContext(product="Clinical View", release="2026.3"),
    )
    return d.model_dump(mode="json")


@pytest.mark.asyncio
async def test_developer_agent_produces_result(graph):
    dispatch = _make_dispatch()
    final = await graph.ainvoke(
        {"dispatch": dispatch},
        config={"configurable": {"thread_id": "dev-t1"}},
    )
    result = final["result"]
    assert result["agent_name"] == AgentName.DEVELOPER.value
    assert result["status"] in (AgentStatus.SUCCESS.value, AgentStatus.PARTIAL.value)
    assert result["confidence"] > 0


@pytest.mark.asyncio
async def test_developer_agent_finds_pr_evidence(graph):
    dispatch = _make_dispatch("Find PRs related to audit trail changes in 2026.3")
    final = await graph.ainvoke(
        {"dispatch": dispatch},
        config={"configurable": {"thread_id": "dev-t2"}},
    )
    assert len(final["result"]["evidence"]) >= 1
