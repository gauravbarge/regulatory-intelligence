"""In-memory message bus tests."""

import pytest

from medidata_common.messaging import InMemoryBus
from medidata_common.topics import Topics


@pytest.mark.asyncio
async def test_produce_and_get_one() -> None:
    bus = InMemoryBus()
    await bus.start()
    await bus.produce(
        topic=str(Topics.TASK_REQUEST),
        value={"request_id": "r1", "hello": "world"},
        key="r1",
    )
    msg = await bus.get_one(str(Topics.TASK_REQUEST))
    assert msg.key == "r1"
    assert msg.value["hello"] == "world"
    await bus.stop()


@pytest.mark.asyncio
async def test_consume_iterates() -> None:
    bus = InMemoryBus()
    await bus.start()
    for i in range(3):
        await bus.produce(str(Topics.AGENT_RESULT), {"i": i}, key=str(i))

    seen = []
    async for msg in bus.consume([str(Topics.AGENT_RESULT)]):
        seen.append(msg.value["i"])
        if len(seen) == 3:
            await bus.stop()
            break
    assert sorted(seen) == [0, 1, 2]
