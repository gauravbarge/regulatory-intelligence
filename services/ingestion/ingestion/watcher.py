"""S3 object watcher.

Polls MinIO/S3 for new objects under a prefix and triggers ingestion.
In production this would consume S3 event notifications via an SQS queue
or MinIO webhook; polling is a simple fallback that works everywhere.
"""

from __future__ import annotations

import asyncio
from typing import Any

from medidata_common.config import Settings
from medidata_common.logging import get_logger

from ingestion.pipeline import IngestionPipeline

_log = get_logger("ingestion.watcher")


class S3PollingWatcher:
    """Polls S3 for new objects and ingests them."""

    def __init__(
        self,
        pipeline: IngestionPipeline,
        settings: Settings,
        prefix: str = "uploads/",
        poll_interval_s: float = 30.0,
    ) -> None:
        self._pipeline = pipeline
        self._settings = settings
        self._prefix = prefix
        self._interval = poll_interval_s
        self._seen: set[str] = set()

    async def run(self) -> None:
        _log.info("watcher.starting", bucket=self._settings.s3_bucket, prefix=self._prefix)
        while True:
            try:
                await self._poll()
            except Exception as exc:
                _log.error("watcher.poll.error", error=str(exc))
            await asyncio.sleep(self._interval)

    async def _poll(self) -> None:
        import asyncio
        objects = await asyncio.to_thread(
            self._pipeline._s3.list_objects,
            self._settings.s3_bucket,
            self._prefix,
        )
        for obj in objects:
            key: str = obj["Key"]
            s3_uri = f"s3://{self._settings.s3_bucket}/{key}"
            if s3_uri in self._seen:
                continue
            self._seen.add(s3_uri)
            _log.info("watcher.new_object", s3_uri=s3_uri)
            try:
                await asyncio.to_thread(self._pipeline.ingest_s3_object, s3_uri)
            except Exception as exc:
                _log.error("watcher.ingest.error", s3_uri=s3_uri, error=str(exc))
