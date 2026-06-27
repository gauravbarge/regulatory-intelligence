"""Environment-driven configuration shared across the Python agent tier."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object. Every value is overridable by environment
    variable (case-insensitive) or a local ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    log_json: bool = False

    # --- Kafka / messaging ---
    kafka_mode: Literal["aiokafka", "memory"] = "memory"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "supervisor"

    # --- Model gateway ---
    model_gateway_mode: Literal["bedrock", "fake"] = "fake"
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_max_tokens: int = 4096
    bedrock_temperature: float = 0.0

    # --- Memory / state ---
    checkpointer_mode: Literal["mongodb", "memory"] = "memory"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "regintel"

    # --- Vector store ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # --- Artifact store ---
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "regintel-artifacts"

    # --- Guardrails ---
    compliance_confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)

    # --- Observability ---
    otel_exporter_otlp_endpoint: str = ""
    langsmith_tracing: bool = False

    @property
    def is_offline(self) -> bool:
        """True when the service can run with no external dependencies."""
        return (
            self.kafka_mode == "memory"
            and self.model_gateway_mode == "fake"
            and self.checkpointer_mode == "memory"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
