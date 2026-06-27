"""Developer Agent host process."""

from __future__ import annotations

import asyncio

from medidata_common.agent_harness import run_agent_app
from medidata_common.audit import AuditEmitter
from medidata_common.config import Settings, get_settings
from medidata_common.contracts import AgentName
from medidata_common.logging import configure_logging, get_logger
from medidata_common.messaging import create_bus

from developer_agent.graph import build_developer_graph

_log = get_logger("developer_agent.app")


async def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    async with create_bus(settings) as bus:
        audit = AuditEmitter(bus)
        graph = build_developer_graph(settings=settings, audit=audit)
        await run_agent_app(AgentName.DEVELOPER, graph, bus, settings.kafka_consumer_group)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
