"""Pick a message-bus implementation from settings."""

from __future__ import annotations

from medidata_common.config import Settings, get_settings
from medidata_common.messaging.base import MessageBus
from medidata_common.messaging.memory import InMemoryBus


def create_bus(settings: Settings | None = None) -> MessageBus:
    """Return a started-on-enter MessageBus based on ``KAFKA_MODE``."""
    settings = settings or get_settings()
    if settings.kafka_mode == "memory":
        return InMemoryBus()

    # Imported lazily so aiokafka is only required when actually used.
    from medidata_common.messaging.kafka import KafkaBus

    return KafkaBus(bootstrap_servers=settings.kafka_bootstrap_servers)
