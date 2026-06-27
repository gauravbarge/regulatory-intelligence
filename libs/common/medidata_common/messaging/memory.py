"""In-process message bus.

A dependency-free implementation backed by per-topic asyncio queues. Lets the
whole agent tier run and be tested without a Kafka broker
(``KAFKA_MODE=memory``).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from medidata_common.messaging.base import Message, MessageBus


class InMemoryBus(MessageBus):
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[Message]] = defaultdict(asyncio.Queue)
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    def _queue(self, topic: str) -> asyncio.Queue[Message]:
        return self._queues[topic]

    async def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        await self._queue(topic).put(
            Message(topic=topic, key=key, value=value, headers=headers or {})
        )

    async def consume(
        self, topics: list[str], group: str | None = None
    ) -> AsyncIterator[Message]:
        queues = [self._queue(t) for t in topics]
        while self._running or any(not q.empty() for q in queues):
            getters = [asyncio.ensure_future(q.get()) for q in queues]
            done, pending = await asyncio.wait(
                getters, return_when=asyncio.FIRST_COMPLETED, timeout=0.5
            )
            for fut in pending:
                fut.cancel()
            for fut in done:
                yield fut.result()

    # Test helper: drain a single message from a topic without a consumer loop.
    async def get_one(self, topic: str, timeout: float = 1.0) -> Message:
        return await asyncio.wait_for(self._queue(topic).get(), timeout=timeout)

    def pending(self, topic: str) -> int:
        return self._queue(topic).qsize()
