"""Developer Agent tools: GitHub repo/PR/commit search.

Stub works offline. Real implementation calls the GitHub REST API via httpx.
Set GITHUB_TOKEN env var for authenticated requests (higher rate limits).
"""

from __future__ import annotations

import os
from typing import Any

from medidata_common.agent_harness import AgentTool
from medidata_common.config import Settings, get_settings
from medidata_common.logging import get_logger

_log = get_logger("developer_agent.tools")


class StubGitHubSearchTool(AgentTool):
    name = "github_search"
    description = (
        "Search GitHub repositories, pull requests, commits, and changed files. "
        "Input: repo (optional), search_terms list, release_tag (optional), jira_key (optional)."
    )

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        query = inputs.get("query", "") or " ".join(inputs.get("search_terms", []))
        release = inputs.get("release_tag", "2026.3")
        items = [
            {
                "id": f"stub-pr-{i}",
                "title": f"[STUB] PR: {query[:40]} (#{100 + i})",
                "body": f"Stub PR body addressing: {query[:80]}",
                "url": f"https://github.com/medidata/clinical-view/pull/{100 + i}",
                "state": "merged",
                "release": release,
                "score": round(0.9 - i * 0.05, 2),
            }
            for i in range(2)
        ]
        return {"results": items, "total": len(items)}


class StubCommitAnalysisTool(AgentTool):
    name = "commit_analysis"
    description = (
        "Analyze changed files and modules in a release commit range. "
        "Input: repo, release_tag, base_tag (optional)."
    )

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        release = inputs.get("release_tag", inputs.get("query", "2026.3"))
        items = [
            {
                "id": f"stub-commit-{i}",
                "title": f"[STUB] Changed module in {release}: module_{i}",
                "snippet": f"Files changed: src/module_{i}/core.py, src/module_{i}/api.py",
                "impact": "medium",
                "score": round(0.85 - i * 0.05, 2),
            }
            for i in range(2)
        ]
        return {"results": items, "total": len(items)}


class GitHubSearchTool(AgentTool):
    """Real GitHub REST API search using httpx."""

    name = "github_search"
    description = (
        "Search GitHub repositories, pull requests, commits, and changed files. "
        "Input: repo (optional), search_terms list, release_tag (optional), jira_key (optional)."
    )

    def __init__(self, token: str | None = None) -> None:
        self._token = token or os.getenv("GITHUB_TOKEN", "")

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        import httpx
        query = inputs.get("query", "") or " ".join(inputs.get("search_terms", []))
        repo = inputs.get("repo", "")
        if repo:
            query = f"repo:{repo} {query}"
        url = "https://api.github.com/search/issues"
        params = {"q": f"{query} is:pr is:merged", "per_page": 5}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                items = [
                    {
                        "id": str(item["number"]),
                        "title": item["title"],
                        "snippet": (item.get("body") or "")[:200],
                        "url": item["html_url"],
                        "state": item["state"],
                        "score": round(item.get("score", 0.8), 4),
                    }
                    for item in data.get("items", [])
                ]
                return {"results": items, "total": data.get("total_count", len(items))}
        except Exception as exc:
            _log.warning("github.search.failed", error=str(exc))
            return await StubGitHubSearchTool().call(inputs)


def create_tools(settings: Settings | None = None) -> list[AgentTool]:
    settings = settings or get_settings()
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        return [GitHubSearchTool(token), StubCommitAnalysisTool()]
    return [StubGitHubSearchTool(), StubCommitAnalysisTool()]
