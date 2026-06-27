"""Research Agent tools: Qdrant semantic search + metadata filter.

Stub implementation works offline with no external services.
Real implementation uses qdrant-client when QDRANT_URL is reachable.
"""

from __future__ import annotations

from typing import Any

from medidata_common.agent_harness import AgentTool
from medidata_common.config import Settings, get_settings
from medidata_common.logging import get_logger

_log = get_logger("research_agent.tools")


class StubRagTool(AgentTool):
    """Deterministic stub returning plausible RAG hits for offline/test runs."""

    name = "rag_search"
    description = (
        "Semantic search over product docs, validation artifacts, release notes, "
        "SOPs and regulatory knowledge. Input: query, filters (product, release, "
        "artifact_type), top_k."
    )

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        query = inputs.get("query", "")
        top_k = int(inputs.get("top_k", 3))
        product = inputs.get("filters", {}).get("product", "Clinical View")
        release = inputs.get("filters", {}).get("release", "2026.3")
        hits = [
            {
                "id": f"stub-doc-{i}",
                "title": f"[STUB] {product} v{release} — {query[:40]} (doc {i})",
                "snippet": (
                    f"Stub evidence for query '{query[:60]}'. "
                    f"This document confirms functionality relevant to the query."
                ),
                "artifact_type": "validation_summary",
                "score": round(0.92 - i * 0.05, 2),
            }
            for i in range(min(top_k, 3))
        ]
        return {"hits": hits, "total": len(hits)}


class QdrantRagTool(AgentTool):
    """Real Qdrant semantic search tool."""

    name = "rag_search"
    description = (
        "Semantic search over product docs, validation artifacts, release notes, "
        "SOPs and regulatory knowledge. Input: query, filters (product, release, "
        "artifact_type), top_k."
    )

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = None
        self._collection = "regintel_docs"
        self._encoder: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from qdrant_client import QdrantClient
            kwargs: dict[str, Any] = {"url": self._settings.qdrant_url}
            if self._settings.qdrant_api_key:
                kwargs["api_key"] = self._settings.qdrant_api_key
            self._client = QdrantClient(**kwargs)
        return self._client

    def _encode(self, text: str) -> list[float]:
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._encoder.encode(text).tolist()

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        query = inputs.get("query", "")
        top_k = int(inputs.get("top_k", 5))
        filters = inputs.get("filters", {})

        try:
            client = self._get_client()
            vector = await asyncio.to_thread(self._encode, query)

            from qdrant_client.models import Filter, FieldCondition, MatchValue
            must = []
            for key in ("product", "release", "artifact_type"):
                if filters.get(key):
                    must.append(FieldCondition(key=key, match=MatchValue(value=filters[key])))
            qdrant_filter = Filter(must=must) if must else None

            results = await asyncio.to_thread(
                client.search,
                collection_name=self._collection,
                query_vector=vector,
                limit=top_k,
                query_filter=qdrant_filter,
            )
            hits = [
                {
                    "id": str(r.id),
                    "title": r.payload.get("title", ""),
                    "snippet": r.payload.get("snippet", r.payload.get("text", ""))[:300],
                    "artifact_type": r.payload.get("artifact_type"),
                    "score": round(r.score, 4),
                }
                for r in results
            ]
            return {"hits": hits, "total": len(hits)}
        except Exception as exc:
            _log.warning("qdrant.search.failed", error=str(exc))
            return await StubRagTool().call(inputs)


class StubKnowledgeBaseTool(AgentTool):
    """Stub keyword search over regulatory/SOP knowledge base."""

    name = "knowledge_base_search"
    description = (
        "Keyword search over SOPs, regulatory guidance, FDA references, "
        "GxP/Part 11 documents. Input: query, category (sop|regulatory|guidance)."
    )

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        query = inputs.get("query", "")
        items = [
            {
                "id": f"kb-{i}",
                "title": f"[STUB] Regulatory reference for: {query[:40]} ({i})",
                "snippet": f"Stub regulatory guidance relevant to '{query[:60]}'.",
                "category": inputs.get("category", "regulatory"),
                "score": round(0.88 - i * 0.04, 2),
            }
            for i in range(2)
        ]
        return {"results": items, "total": len(items)}


def create_tools(settings: Settings | None = None) -> list[AgentTool]:
    settings = settings or get_settings()
    try:
        import qdrant_client  # noqa: F401
        return [QdrantRagTool(settings), StubKnowledgeBaseTool()]
    except ImportError:
        return [StubRagTool(), StubKnowledgeBaseTool()]
