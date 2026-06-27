"""Agile Master Agent tools: Jira search — stories, epics, bugs, roadmap.

Stub works offline. Real implementation calls Jira REST API via httpx.
Set JIRA_BASE_URL, JIRA_USER and JIRA_API_TOKEN env vars for real calls.
"""

from __future__ import annotations

import os
from typing import Any

from medidata_common.agent_harness import AgentTool
from medidata_common.config import Settings, get_settings
from medidata_common.logging import get_logger

_log = get_logger("agile_master_agent.tools")


class StubJiraSearchTool(AgentTool):
    name = "jira_search"
    description = (
        "Search Jira issues: stories, epics, bugs, defects and roadmap items. "
        "Input: query, project (optional), release (optional), issue_types list."
    )

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        query = inputs.get("query", "")
        release = inputs.get("release", "2026.3")
        items = [
            {
                "id": f"MDV-{100 + i}",
                "key": f"MDV-{100 + i}",
                "title": f"[STUB] {inputs.get('issue_types', ['Story'])[0]}: {query[:40]} ({i})",
                "body": f"Stub Jira issue body for: {query[:80]}. Release: {release}.",
                "status": "Done" if i == 0 else "In Progress",
                "issue_type": (inputs.get("issue_types") or ["Story"])[0],
                "release": release,
                "score": round(0.91 - i * 0.06, 2),
            }
            for i in range(2)
        ]
        return {"results": items, "total": len(items)}


class StubRoadmapTool(AgentTool):
    name = "roadmap_lookup"
    description = (
        "Look up product roadmap items, planned features and delivery timelines. "
        "Input: query, product (optional), release (optional)."
    )

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        query = inputs.get("query", "")
        items = [
            {
                "id": f"ROAD-{i}",
                "title": f"[STUB] Roadmap item: {query[:40]}",
                "snippet": f"Planned for next release. Addresses: {query[:60]}.",
                "status": "planned",
                "score": round(0.80 - i * 0.05, 2),
            }
            for i in range(2)
        ]
        return {"results": items, "total": len(items)}


class JiraSearchTool(AgentTool):
    """Real Jira REST API search via httpx."""

    name = "jira_search"
    description = (
        "Search Jira issues: stories, epics, bugs, defects and roadmap items. "
        "Input: query, project (optional), release (optional), issue_types list."
    )

    def __init__(self, base_url: str, user: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._auth = (user, token)

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        import httpx
        query = inputs.get("query", "")
        project = inputs.get("project", "")
        release = inputs.get("release", "")
        types = inputs.get("issue_types", [])

        jql_parts = [f'text ~ "{query}"']
        if project:
            jql_parts.append(f'project = "{project}"')
        if release:
            jql_parts.append(f'fixVersion = "{release}"')
        if types:
            type_str = ", ".join(f'"{t}"' for t in types)
            jql_parts.append(f"issuetype in ({type_str})")
        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

        try:
            async with httpx.AsyncClient(timeout=15.0, auth=self._auth) as client:
                resp = await client.get(
                    f"{self._base}/rest/api/3/search",
                    params={"jql": jql, "maxResults": 5, "fields": "summary,description,status,issuetype,fixVersions"},
                )
                resp.raise_for_status()
                data = resp.json()
                items = [
                    {
                        "id": issue["id"],
                        "key": issue["key"],
                        "title": issue["fields"]["summary"],
                        "snippet": str(issue["fields"].get("description") or "")[:200],
                        "status": issue["fields"]["status"]["name"],
                        "issue_type": issue["fields"]["issuetype"]["name"],
                        "score": 0.85,
                    }
                    for issue in data.get("issues", [])
                ]
                return {"results": items, "total": data.get("total", len(items))}
        except Exception as exc:
            _log.warning("jira.search.failed", error=str(exc))
            return await StubJiraSearchTool().call(inputs)


def create_tools(settings: Settings | None = None) -> list[AgentTool]:
    base_url = os.getenv("JIRA_BASE_URL", "")
    user = os.getenv("JIRA_USER", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    if base_url and user and token:
        return [JiraSearchTool(base_url, user, token), StubRoadmapTool()]
    return [StubJiraSearchTool(), StubRoadmapTool()]
