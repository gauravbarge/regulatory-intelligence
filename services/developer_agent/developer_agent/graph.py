"""Developer agent LangGraph graph builder."""

from __future__ import annotations

from typing import Any

from medidata_common.agent_harness import AgentTool, build_agent_graph
from medidata_common.config import Settings, get_settings
from medidata_common.contracts import AgentName

from developer_agent.tools import create_tools


def build_developer_graph(
    settings: Settings | None = None,
    tools: list[AgentTool] | None = None,
    model: Any = None,
    audit: Any = None,
    checkpointer: Any = None,
):
    settings = settings or get_settings()
    if model is None and settings.model_gateway_mode == "bedrock":
        from langchain_aws import ChatBedrockConverse
        model = ChatBedrockConverse(
            model=settings.bedrock_model_id,
            region_name=settings.aws_region,
            max_tokens=1024,
            temperature=0.0,
        )
    return build_agent_graph(
        agent_name=AgentName.DEVELOPER,
        tools=tools or create_tools(settings),
        model=model,
        audit=audit,
        checkpointer=checkpointer,
    )
