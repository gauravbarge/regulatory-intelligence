"""Supervisor host process.

Consumes ``task.request`` from Kafka, runs each request through the compiled
supervisor graph, publishes the final response to ``ui.inbound.response`` and
dead-letters unrecoverable failures. In ``KAFKA_MODE=memory`` /
``MODEL_GATEWAY_MODE=fake`` the whole thing runs with no external services.
"""

from __future__ import annotations

import asyncio
import contextlib

from medidata_common.audit import AuditEmitter
from medidata_common.config import Settings, get_settings
from medidata_common.contracts import DeadLetter
from medidata_common.logging import configure_logging, get_logger
from medidata_common.messaging import create_bus
from medidata_common.messaging.base import MessageBus
from medidata_common.topics import Topics

from supervisor.dispatcher import BusAgentRunner, LocalStubAgentRunner
from supervisor.graph import build_default

log = get_logger("supervisor.app")


async def _process_one(graph, bus: MessageBus, value: dict) -> None:
    request_id = value.get("request_id", "unknown")
    config = {"configurable": {"thread_id": request_id}}
    final_state = await graph.ainvoke({"request": value}, config=config)
    response = final_state.get("final_response", {})
    await bus.produce(
        topic=str(Topics.UI_INBOUND_RESPONSE),
        value=response,
        key=request_id,
    )
    log.info(
        "request.completed",
        request_id=request_id,
        decision=response.get("decision"),
    )


async def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)
    log.info(
        "supervisor.starting",
        env=settings.app_env,
        kafka_mode=settings.kafka_mode,
        model_mode=settings.model_gateway_mode,
        checkpointer=settings.checkpointer_mode,
    )

    bus = create_bus(settings)
    await bus.start()
    audit = AuditEmitter(bus)

    # Distributed dispatch when a real broker is configured; stub otherwise.
    bus_runner: BusAgentRunner | None = None
    if settings.kafka_mode == "aiokafka":
        bus_runner = BusAgentRunner(bus)
        await bus_runner.start()
        runner = bus_runner
    else:
        runner = LocalStubAgentRunner()

    from supervisor.memory import checkpointer as checkpointer_cm

    with checkpointer_cm(settings) as cp:
        graph = build_default(settings, runner=runner, audit=audit, checkpointer=cp)
        try:
            async for msg in bus.consume(
                [str(Topics.TASK_REQUEST)], group=settings.kafka_consumer_group
            ):
                try:
                    await _process_one(graph, bus, msg.value)
                except Exception as exc:  # noqa: BLE001 - route to DLQ
                    log.error("request.failed", error=str(exc))
                    await bus.produce(
                        topic=str(Topics.DEAD_LETTER),
                        value=DeadLetter(
                            request_id=msg.value.get("request_id", "unknown"),
                            agent_name="supervisor",
                            payload=msg.value,
                            error=str(exc),
                        ).model_dump(mode="json"),
                        key=msg.value.get("request_id"),
                    )
        finally:
            if bus_runner:
                await bus_runner.stop()
            with contextlib.suppress(Exception):
                await bus.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
