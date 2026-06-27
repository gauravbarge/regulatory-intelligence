# RAG Ingestion Pipeline

## Document Sources
- Product user guides
- Release notes
- Validation Summary Reports
- RTMs
- Test evidence
- SOPs
- Known issue documents
- Support KBs
- Customer RFPs
- Implementation guides

## Pipeline Steps
1. Upload raw file to S3
2. Extract text and metadata
3. Chunk document by semantic section
4. Detect artifact type
5. Generate embeddings
6. Store embeddings in Qdrant
7. Store metadata in MongoDB
8. Keep raw artifact in S3
9. Record audit event

## Required Metadata
- product
- release
- document_type
- version
- effective_date
- source_system
- confidentiality_level
- customer_id if customer-specific
- validation_status

## Retrieval Requirements
- Must return citations
- Must preserve document version
- Must support release filtering
- Must support tenant/customer isolation
