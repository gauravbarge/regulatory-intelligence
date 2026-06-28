"""RAG Ingestion Pipeline.

Watches S3/MinIO for new documents, extracts text, chunks by semantic
section, generates embeddings, and upserts into Qdrant with full metadata.

Pipeline steps (rag-ingestion-pipeline.md):
  1. Detect new file in S3 (via S3 event notification or polling)
  2. Extract text + metadata
  3. Chunk by semantic section (paragraph/heading boundaries)
  4. Detect artifact type
  5. Generate embeddings
  6. Upsert into Qdrant
  7. Record audit event
"""

from __future__ import annotations

import hashlib
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from medidata_common.config import Settings
from medidata_common.logging import get_logger

_log = get_logger("ingestion.pipeline")

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any]
    embedding: list[float] = field(default_factory=list)


@dataclass
class DocumentMeta:
    document_id: str
    s3_uri: str
    filename: str
    artifact_type: str
    product: str | None
    release: str | None
    effective_date: str | None
    confidentiality_level: str
    customer_id: str | None
    validation_status: str
    ingested_at: str


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text(data: bytes, filename: str) -> str:
    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n\n".join(p.extract_text() or "" for p in reader.pages)
        except ImportError:
            _log.warning("pypdf not installed; falling back to raw decode")
    if filename.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            _log.warning("python-docx not installed; falling back to raw decode")
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Artifact type detection
# ---------------------------------------------------------------------------

_ARTIFACT_PATTERNS: list[tuple[str, list[str]]] = [
    ("validation_summary", ["validation summary", "vsummary", "ivr", "installation qualification"]),
    ("release_notes", ["release note", "what's new", "change log", "changelog"]),
    ("rtm", ["requirements traceability", "rtm", "traceability matrix"]),
    ("sop", ["standard operating procedure", "sop ", "s.o.p"]),
    ("test_report", ["test report", "test evidence", "execution report", "iq ", "oq ", "pq "]),
    ("rfp", ["request for proposal", "rfp", "requirements document", "functional specification"]),
    ("user_guide", ["user guide", "user manual", "administrator guide"]),
    ("known_issues", ["known issue", "known defect", "outstanding issue"]),
]


def detect_artifact_type(filename: str, text_preview: str) -> str:
    combined = (filename + " " + text_preview[:500]).lower()
    for artifact_type, patterns in _ARTIFACT_PATTERNS:
        if any(p in combined for p in patterns):
            return artifact_type
    return "unknown"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,4}\s+.+|^[A-Z][A-Z\s]{5,}$", re.MULTILINE)
_MIN_CHUNK = 150
_MAX_CHUNK = 1200


def chunk_text(text: str) -> list[str]:
    """Split text at heading/paragraph boundaries into semantic chunks."""
    # Split on double newlines first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        is_heading = bool(_HEADING_RE.match(para)) or len(para) < 80
        if is_heading and current and len(current) >= _MIN_CHUNK:
            chunks.append(current.strip())
            current = para + "\n\n"
        elif len(current) + len(para) > _MAX_CHUNK and len(current) >= _MIN_CHUNK:
            chunks.append(current.strip())
            current = para + "\n\n"
        else:
            current += para + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    # Filter out very short chunks
    return [c for c in chunks if len(c) >= _MIN_CHUNK]


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

class EmbeddingModel:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._get_model().encode(texts, show_progress_bar=False).tolist()

    @property
    def dimension(self) -> int:
        return self._get_model().get_sentence_embedding_dimension()


# ---------------------------------------------------------------------------
# Qdrant upsert
# ---------------------------------------------------------------------------

class QdrantIngester:
    COLLECTION = "regintel_docs"

    def __init__(self, settings: Settings, embedding_model: EmbeddingModel) -> None:
        self._settings = settings
        self._model = embedding_model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from qdrant_client import QdrantClient
            kwargs: dict[str, Any] = {"url": self._settings.qdrant_url}
            if self._settings.qdrant_api_key:
                kwargs["api_key"] = self._settings.qdrant_api_key
            self._client = QdrantClient(**kwargs)
        return self._client

    def ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams
        client = self._get_client()
        existing = [c.name for c in client.get_collections().collections]
        if self.COLLECTION not in existing:
            client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(size=self._model.dimension, distance=Distance.COSINE),
            )
            _log.info("qdrant.collection.created", collection=self.COLLECTION)

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> None:
        from qdrant_client.models import PointStruct
        client = self._get_client()
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, c.chunk_id)),
                vector=c.embedding,
                payload={
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "text": c.text,
                    "snippet": c.text[:300],
                    **c.metadata,
                },
            )
            for c in chunks
        ]
        client.upsert(collection_name=self.COLLECTION, points=points)
        _log.info("qdrant.upsert", count=len(points))


# ---------------------------------------------------------------------------
# S3 client
# ---------------------------------------------------------------------------

class S3Client:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = None

    def _get(self) -> Any:
        if self._client is None:
            import boto3
            kwargs: dict[str, Any] = {}
            if self._settings.s3_endpoint_url:
                kwargs["endpoint_url"] = self._settings.s3_endpoint_url
            self._client = boto3.client("s3", region_name=self._settings.aws_region, **kwargs)
        return self._client

    def download(self, bucket: str, key: str) -> bytes:
        obj = self._get().get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()

    def list_objects(self, bucket: str, prefix: str = "") -> list[dict[str, Any]]:
        resp = self._get().list_objects_v2(Bucket=bucket, Prefix=prefix)
        return resp.get("Contents", [])


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class IngestionPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._s3 = S3Client(settings)
        self._embed = EmbeddingModel()
        self._qdrant = QdrantIngester(settings, self._embed)

    def initialize(self) -> None:
        self._qdrant.ensure_collection()

    def ingest_s3_object(
        self,
        s3_uri: str,
        metadata_overrides: dict[str, Any] | None = None,
    ) -> DocumentMeta:
        # Parse s3://bucket/key
        without_scheme = s3_uri.replace("s3://", "")
        bucket, _, key = without_scheme.partition("/")
        filename = key.split("/")[-1]

        _log.info("ingestion.start", s3_uri=s3_uri)
        data = self._s3.download(bucket, key)
        text = extract_text(data, filename)

        artifact_type = (metadata_overrides or {}).get("artifact_type") or detect_artifact_type(filename, text)

        doc_id = hashlib.sha256(s3_uri.encode()).hexdigest()[:16]
        meta: dict[str, Any] = {
            "s3_uri": s3_uri,
            "filename": filename,
            "artifact_type": artifact_type,
            "product": None,
            "release": None,
            "effective_date": None,
            "confidentiality_level": "internal",
            "customer_id": None,
            "validation_status": "active",
        }
        if metadata_overrides:
            meta.update({k: v for k, v in metadata_overrides.items() if v is not None})

        chunks_text = chunk_text(text)
        if not chunks_text:
            _log.warning("ingestion.no_chunks", s3_uri=s3_uri)
            chunks_text = [text[:_MAX_CHUNK]] if text.strip() else []

        embeddings = self._embed.embed(chunks_text) if chunks_text else []
        chunks = [
            DocumentChunk(
                chunk_id=f"{doc_id}-{i}",
                document_id=doc_id,
                text=t,
                metadata={**meta, "chunk_index": i, "total_chunks": len(chunks_text)},
                embedding=embeddings[i],
            )
            for i, t in enumerate(chunks_text)
        ]

        if chunks:
            self._qdrant.upsert_chunks(chunks)

        doc_meta = DocumentMeta(
            document_id=doc_id,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            **{k: meta.get(k) for k in DocumentMeta.__dataclass_fields__ if k not in ("document_id", "ingested_at")},  # type: ignore[arg-type]
        )
        _log.info(
            "ingestion.complete",
            s3_uri=s3_uri,
            chunks=len(chunks),
            artifact_type=artifact_type,
        )
        return doc_meta
