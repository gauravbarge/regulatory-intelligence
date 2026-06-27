"""Contract model tests."""

from medidata_common.contracts import (
    AgentName,
    AgentResult,
    AgentStatus,
    SupervisorRequest,
    UseCase,
)


def test_supervisor_request_defaults() -> None:
    req = SupervisorRequest(
        user_id="u1", tenant_id="t1", user_query="Does product X support audit trails?"
    )
    assert req.request_id  # auto-generated
    assert req.use_case is None  # classified later
    assert req.context.product is None


def test_agent_result_roundtrip() -> None:
    res = AgentResult(
        agent_name=AgentName.RESEARCH,
        task_id="d1",
        request_id="r1",
        status=AgentStatus.SUCCESS,
        confidence=0.9,
        summary="Found supporting evidence.",
    )
    dumped = res.model_dump(mode="json")
    assert dumped["agent_name"] == "research_agent"
    assert dumped["status"] == "success"

    restored = AgentResult.model_validate(dumped)
    assert restored.agent_name is AgentName.RESEARCH
    assert restored.confidence == 0.9


def test_use_case_values() -> None:
    assert UseCase.REQUIREMENT_VALIDATION.value == "requirement_validation"
    assert UseCase.RELEASE_VALIDATION.value == "release_validation"
