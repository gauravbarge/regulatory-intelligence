"""Checkpointer (working-memory) factory for the supervisor graph.

LangGraph checkpointers persist graph state after every node, giving the
supervisor durable, resumable runs. ``memory`` uses the in-process saver;
``mongodb`` uses the LangGraph Mongo checkpointer (lazy import).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from medidata_common.config import Settings, get_settings


@contextmanager
def checkpointer(settings: Settings | None = None) -> Iterator[Any]:
    """Yield a LangGraph checkpointer appropriate for the configured mode."""
    settings = settings or get_settings()

    if settings.checkpointer_mode == "mongodb":
        from langgraph.checkpoint.mongodb import MongoDBSaver  # lazy

        with MongoDBSaver.from_conn_string(
            settings.mongodb_uri, db_name=settings.mongodb_db
        ) as saver:
            yield saver
        return

    from langgraph.checkpoint.memory import MemorySaver

    yield MemorySaver()
