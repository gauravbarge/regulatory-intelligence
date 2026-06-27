"""Kafka-backed message bus using aiokafka.

Used when ``KAFKA_MODE=aiokafka``. JSON (orjson) encoded values; the message
key is the ``request_id`` so all events for one request land on the same
partition and preserve ordering.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import orjson

from medidata_common.messaging.base import Message, MessageBus


class KafkaBus(MessageBus):
    def __init__(self, bootstrap_servers: str, client_id: str = "regintel") -> None:
        self._bootstrap = bootstrap_servers
        self._client_id = client_id
        self._producer: Any = None

    async def start(self) -> None:
        from aiokafka import AIOKafkaProducer

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap,
            client_id=self._client_id,
            value_serializer=lambda v: orjson.dumps(v),
            key_serializer=lambda k: k.encode() if k else None,
            enable_idempotence=True,
            acks="all",
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def produce(
        self,
        topic: str,
        value: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        assert self._producer is not None, "KafkaBus not started"
        kafka_headers = [(k, v.encode()) for k, v in (headers or {}).items()]
        await self._producer.send_and_wait(
            topic, value=value, key=key, headers=kafka_headers
        )

    async def consume(
        self, topics: list[str], group: str | None = None
    ) -> AsyncIterator[Message]:
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self._bootstrap,
            group_id=group or "regintel",
            client_id=self._client_id,
            value_deserializer=lambda v: orjson.loads(v),
            key_deserializer=lambda k: k.decode() if k else None,
            enable_auto_commit=True,
            auto_offset_reset="earliest",
        )
        await consumer.start()
        try:
            async for rec in consumer:
                yield Message(
                    topic=rec.topic,
                    key=rec.key,
                    value=rec.value,
                    headers={k: v.decode() for k, v in (rec.headers or [])},
                )
        finally:
            await consumer.stop()
