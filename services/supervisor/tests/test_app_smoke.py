"""Host smoke test: a task.request flows to a ui.inbound.response."""

import asyncio

import pytest

from medidata_common.config import Settings
from medidata_common.contracts import SupervisorRequest
from medidata_common.messaging import InMemoryBus
from medidata_common.topics import Topics

from supervisor.app import _process_one
from supervisor.dispatcher import LocalStubAgentRunner
from supervisor.graph import build_default


@pytest.mark.asyncio
async def test_process_one_publishes_response() -> None:
    settings = Settings(kafka_mode="memory", model_gateway_mode="fake",
                        checkpointer_mode="memory")
    bus = InMemoryBus()
    await bus.start()
    graph = build_default(settings, runner=LocalStubAgentRunner(confidence=0.9))

    req = SupervisorRequest(user_id="u1", tenant_id="t1",
                            user_query="Does it support e-signatures?")
    await _process_one(graph, bus, req.model_dump(mode="json"))

    msg = await asyncio.wait_for(bus.get_one(str(Topics.UI_INBOUND_RESPONSE)), timeout=2)
    assert msg.value["request_id"] == req.request_id
    assert msg.value["decision"] in {
        "supported", "partially_supported", "unsupported", "human_review_required"
    }
    await bus.stop()
