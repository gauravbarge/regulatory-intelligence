"""Shared library for the Regulatory Intelligence platform.

Exposes the cross-service contracts, configuration, structured logging,
Kafka topic names, audit events and the message-bus abstraction used by the
Python agent tier.
"""

from medidata_common.agent_harness import AgentTool, AgentState, build_agent_graph, run_agent_app
from medidata_common.config import Settings, get_settings
from medidata_common.topics import Topics

__all__ = [
    "AgentTool", "AgentState", "build_agent_graph", "run_agent_app",
    "Settings", "get_settings", "Topics",
]
__version__ = "0.1.0"
