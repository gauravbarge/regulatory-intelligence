"""Document Analyst agent smoke tests."""

import pytest
from medidata_common.contracts import AgentName, AgentStatus, UseCase

from document_analyst.graph import build_document_analyst_graph
from document_analyst.tools import StubDocumentParserTool, StubRequirementClassifierTool


@pytest.fixture
def graph():
    return build_document_analyst_graph(
        tools=[StubDocumentParserTool(), StubRequirementClassifierTool()]
    )


def _make_dispatch(objective: str = "Extract requirements from RFP for audit trail") -> dict:
    from medidata_common.contracts import AgentDispatch, RequestContext
    d = AgentDispatch(
        request_id="req-doc-001",
        tenant_id="tenant-test",
        agent_name=AgentName.DOCUMENT_ANALYST,
        use_case=UseCase.REQUIREMENT_VALIDATION,
        objective=objective,
        context=RequestContext(product="Clinical View"),
        inputs={"s3_uri": "s3://regintel-artifacts/rfp-sample.pdf", "document_type": "rfp"},
    )
    return d.model_dump(mode="json")


@pytest.mark.asyncio
async def test_document_analyst_produces_result(graph):
    dispatch = _make_dispatch()
    final = await graph.ainvoke(
        {"dispatch": dispatch},
        config={"configurable": {"thread_id": "doc-t1"}},
    )
    result = final["result"]
    assert result["agent_name"] == AgentName.DOCUMENT_ANALYST.value
    assert result["status"] in (AgentStatus.SUCCESS.value, AgentStatus.PARTIAL.value)
    assert result["confidence"] > 0


@pytest.mark.asyncio
async def test_document_analyst_extracts_requirements(graph):
    dispatch = _make_dispatch("Extract GxP requirements from uploaded validation package")
    final = await graph.ainvoke(
        {"dispatch": dispatch},
        config={"configurable": {"thread_id": "doc-t2"}},
    )
    result = final["result"]
    assert len(result["evidence"]) >= 1
    assert result["findings"][0]["confidence"] > 0
