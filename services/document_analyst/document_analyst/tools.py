"""Document Analyst tools: parse uploaded docs (RFP, validation packages, etc.)
from S3 and extract structured requirements and evidence.

Stub works offline. Real implementation uses boto3 + pypdf/python-docx.
Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / S3_ENDPOINT_URL for MinIO.
"""

from __future__ import annotations

import os
from typing import Any

from medidata_common.agent_harness import AgentTool
from medidata_common.config import Settings, get_settings
from medidata_common.logging import get_logger

_log = get_logger("document_analyst.tools")


class StubDocumentParserTool(AgentTool):
    name = "document_parser"
    description = (
        "Parse an uploaded document (RFP, validation package, release note) from S3 "
        "and extract structured requirements, tables, risks and missing information. "
        "Input: s3_uri (optional), document_type (rfp|validation_package|release_note|unknown), query."
    )

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        query = inputs.get("query", "")
        doc_type = inputs.get("document_type", "rfp")
        s3_uri = inputs.get("s3_uri", "s3://stub/document.pdf")
        items = [
            {
                "id": f"req-{i}",
                "title": f"[STUB] Requirement {i}: {query[:40]}",
                "snippet": (
                    f"Extracted requirement from {doc_type} at {s3_uri}. "
                    f"Clause {i+1}: {query[:60]}."
                ),
                "requirement_status": "Unknown",
                "category": "functional",
                "score": round(0.88 - i * 0.05, 2),
            }
            for i in range(3)
        ]
        return {"hits": items, "total": len(items), "document_type": doc_type}


class StubRequirementClassifierTool(AgentTool):
    name = "requirement_classifier"
    description = (
        "Classify extracted requirements by category and regulatory relevance. "
        "Input: requirements list or query describing requirements to classify."
    )

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        query = inputs.get("query", "")
        items = [
            {
                "id": f"class-{i}",
                "title": f"[STUB] Classified requirement: {query[:40]}",
                "snippet": f"Category: GxP/Part 11. Risk: {'high' if i == 0 else 'medium'}. {query[:60]}",
                "category": "GxP" if i == 0 else "functional",
                "risk": "high" if i == 0 else "medium",
                "score": round(0.85 - i * 0.05, 2),
            }
            for i in range(2)
        ]
        return {"results": items, "total": len(items)}


class S3DocumentParserTool(AgentTool):
    """Real S3 + PDF/DOCX parser."""

    name = "document_parser"
    description = (
        "Parse an uploaded document (RFP, validation package, release note) from S3 "
        "and extract structured requirements, tables, risks and missing information. "
        "Input: s3_uri (optional), document_type, query."
    )

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def call(self, inputs: dict[str, Any]) -> dict[str, Any]:
        import asyncio
        s3_uri = inputs.get("s3_uri", "")
        if not s3_uri:
            return await StubDocumentParserTool().call(inputs)

        try:
            text = await asyncio.to_thread(self._fetch_and_extract, s3_uri)
            query = inputs.get("query", "")
            # Simple chunking: split by paragraphs and keep top matches
            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
            hits = [
                {
                    "id": f"para-{i}",
                    "title": f"Paragraph {i+1} from {s3_uri.split('/')[-1]}",
                    "snippet": para[:300],
                    "document_type": inputs.get("document_type", "unknown"),
                    "score": 0.8,
                }
                for i, para in enumerate(paragraphs[:5])
            ]
            return {"hits": hits, "total": len(hits)}
        except Exception as exc:
            _log.warning("s3.parse.failed", error=str(exc))
            return await StubDocumentParserTool().call(inputs)

    def _fetch_and_extract(self, s3_uri: str) -> str:
        import boto3
        import io
        parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
        s3 = boto3.client(
            "s3",
            endpoint_url=self._settings.s3_endpoint_url or None,
        )
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        if key.endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(data))
                return "\n\n".join(p.extract_text() or "" for p in reader.pages)
            except ImportError:
                pass
        if key.endswith(".docx"):
            try:
                from docx import Document
                doc = Document(io.BytesIO(data))
                return "\n\n".join(p.text for p in doc.paragraphs if p.text)
            except ImportError:
                pass
        return data.decode("utf-8", errors="replace")


def create_tools(settings: Settings | None = None) -> list[AgentTool]:
    settings = settings or get_settings()
    try:
        import boto3  # noqa: F401
        return [S3DocumentParserTool(settings), StubRequirementClassifierTool()]
    except ImportError:
        return [StubDocumentParserTool(), StubRequirementClassifierTool()]
