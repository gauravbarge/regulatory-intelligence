"""Shared Supervisor harness.

A LangGraph ``StateGraph`` that classifies a request, plans sub-tasks,
dispatches them to specialist agent graphs, aggregates structured results,
synthesizes a final response, and enforces guardrails / human-in-the-loop.
"""

from supervisor.graph import build_supervisor_graph

__all__ = ["build_supervisor_graph"]
__version__ = "0.1.0"
