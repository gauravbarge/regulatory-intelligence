"""Message-bus interface shared by the in-memory and Kafka implementations."""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Message:
    """A consumed message."""

    topic: str
    key: str | None
    value: dict[str, Any]
    headers: dict[str, str]


# A handler returns nothing; raising re-queues / dead-letters per caller policy.
Handler = Callable[[Message], "Any"]


class MessageBus(abc.ABC):
    """Async producer/consumer abstraction.

    Implementations: :class:`~medidata_common.messaging.memory.InMemoryBus`
    and :class:`~medidata_common.messaging.kafka.KafkaBus`.
    """

    @abc.abstractmethod
    async def start(self) -> None: ...

    @abc.abstractmethod
    async def stop(self) -> None: ...

    @abc.abstractmethod
    async def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None: ...

    @abc.abstractmethod
    def consume(
        self, topics: list[str], group: str | None = None
    ) -> AsyncIterator[Message]:
        """Async-iterate messages from ``topics``."""
        ...

    async def __aenter__(self) -> "MessageBus":
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()
