"""Ingestion service entry point.

Starts the S3 polling watcher. In production, configure S3/MinIO to send
event notifications and replace polling with event consumption.
"""

from __future__ import annotations

import asyncio
import os

from medidata_common.config import Settings, get_settings
from medidata_common.logging import configure_logging, get_logger

from ingestion.pipeline import IngestionPipeline
from ingestion.watcher import S3PollingWatcher

_log = get_logger("ingestion.app")


async def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    prefix = os.getenv("INGESTION_WATCH_PREFIX", "uploads/")
    poll_interval = float(os.getenv("INGESTION_POLL_INTERVAL_S", "30"))

    _log.info(
        "ingestion.starting",
        bucket=settings.s3_bucket,
        prefix=prefix,
        qdrant_url=settings.qdrant_url,
    )

    pipeline = IngestionPipeline(settings)
    try:
        pipeline.initialize()
    except Exception as exc:
        _log.warning("ingestion.init.failed", error=str(exc), msg="will retry on first poll")

    watcher = S3PollingWatcher(pipeline, settings, prefix=prefix, poll_interval_s=poll_interval)
    await watcher.run()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
