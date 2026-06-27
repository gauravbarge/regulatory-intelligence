"""End-to-end supervisor graph runs in fully offline mode."""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from medidata_common.audit import AuditEmitter
from medidata_common.config import Settings
from medidata_common.contracts import SupervisorRequest, UseCase
from medidata_common.messaging import InMemoryBus
from medidata_common.topics import Topics

from supervisor.dispatcher import LocalStubAgentRunner
from supervisor.graph import build_default


def _settings(**kw) -> Settings:
    base = dict(
        kafka_mode="memory",
        model_gateway_mode="fake",
        checkpointer_mode="memory",
        compliance_confidence_threshold=0.8,
    )
    base.update(kw)
    return Settings(**base)


@pytest.mark.asyncio
async def test_requirement_validation_end_to_end() -> None:
    graph = build_default(
        _settings(), runner=LocalStubAgentRunner(confidence=0.9), checkpointer=MemorySaver()
    )
    req = SupervisorRequest(
        user_id="u1",
        tenant_id="t1",
        user_query="Does Clinical View support audit trails?",
        context={"product": "Clinical View"},
    )
    state = await graph.ainvoke(
        {"request": req.model_dump(mode="json")},
        config={"configurable": {"thread_id": req.request_id}},
    )

    assert state["use_case"] == UseCase.REQUIREMENT_VALIDATION.value
    # four specialist agents dispatched
    assert len(state["plan"]) == 4
    assert len(state["agent_results"]) == 4
    final = state["final_response"]
    assert final["request_id"] == req.request_id
    # high stub confidence (0.9) >= 0.8 threshold -> supported, auto-released
    assert final["decision"] == "supported"
    assert final["human_approval"]["required"] is False


@pytest.mark.asyncio
async def test_low_confidence_routes_to_human_review() -> None:
    graph = build_default(
        _settings(), runner=LocalStubAgentRunner(confidence=0.4), checkpointer=MemorySaver()
    )
    req = SupervisorRequest(
        user_id="u1",
        tenant_id="t1",
        user_query="Is patient data integrity preserved?",
    )
    state = await graph.ainvoke(
        {"request": req.model_dump(mode="json")},
        config={"configurable": {"thread_id": req.request_id}},
    )
    final = state["final_response"]
    assert final["decision"] == "human_review_required"
    assert final["human_approval"]["required"] is True
    assert final["human_approval"]["status"] == "pending"


@pytest.mark.asyncio
async def test_audit_events_emitted() -> None:
    bus = InMemoryBus()
    await bus.start()
    audit = AuditEmitter(bus)
    graph = build_default(
        _settings(), runner=LocalStubAgentRunner(confidence=0.9), audit=audit,
        checkpointer=MemorySaver(),
    )
    req = SupervisorRequest(user_id="u1", tenant_id="t1", user_query="audit trail support?")
    await graph.ainvoke(
        {"request": req.model_dump(mode="json")},
        config={"configurable": {"thread_id": req.request_id}},
    )
    actions = []
    while bus.pending(str(Topics.AUDIT_EVENT)):
        msg = await bus.get_one(str(Topics.AUDIT_EVENT))
        actions.append(msg.value["action"])
    await bus.stop()

    for expected in ("user_request", "classification", "plan", "agent_dispatch",
                     "model_output", "guardrail_decision", "final_response"):
        assert expected in actions, f"missing audit action {expected}"
