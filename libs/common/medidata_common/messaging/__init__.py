"""Message-bus abstraction over Kafka with an in-process fallback."""

from medidata_common.messaging.base import Message, MessageBus
from medidata_common.messaging.factory import create_bus
from medidata_common.messaging.memory import InMemoryBus

__all__ = ["Message", "MessageBus", "InMemoryBus", "create_bus"]
