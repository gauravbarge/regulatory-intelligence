"""LangGraph state for the supervisor graph.

The state is a ``TypedDict``. List fields that several nodes append to use an
``add`` reducer so concurrent/successive writes accumulate instead of
overwrite.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class SupervisorState(TypedDict, total=False):
    # --- request ---
    request: dict[str, Any]          # SupervisorRequest (json)
    request_id: str
    tenant_id: str
    user_id: str
    user_query: str
    context: dict[str, Any]          # RequestContext (json)

    # --- classification & planning ---
    use_case: str | None             # UseCase value
    plan: list[dict[str, Any]]       # planned AgentDispatch dicts

    # --- execution ---
    agent_results: Annotated[list[dict[str, Any]], operator.add]

    # --- synthesis & governance ---
    draft_response: dict[str, Any]   # SupervisorResponse (json, pre-guardrail)
    guardrail: dict[str, Any]        # GuardrailResult (json)
    final_response: dict[str, Any]   # SupervisorResponse (json, final)

    # --- diagnostics ---
    errors: Annotated[list[str], operator.add]
