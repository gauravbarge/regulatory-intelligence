# MCP Interface Specifications

## Jira MCP
Capabilities:
- Search issues
- Retrieve epics/stories/bugs
- Map release to stories
- Identify open defects
- Return roadmap status

Inputs:
```json
{
  "query": "string",
  "project": "optional",
  "release": "optional",
  "issue_types": ["Story", "Bug", "Epic"]
}
```

## GitHub MCP
Capabilities:
- Search repositories
- Search pull requests
- Inspect commits
- Identify changed files
- Link code to Jira keys

Inputs:
```json
{
  "repo": "string",
  "release_tag": "optional",
  "jira_key": "optional",
  "search_terms": []
}
```

## RAG/Qdrant MCP
Capabilities:
- Semantic search
- Hybrid keyword + vector retrieval
- Return cited chunks
- Filter by artifact type, product, release

Inputs:
```json
{
  "query": "string",
  "filters": {
    "product": "Clinical View",
    "release": "2026.3",
    "artifact_type": "validation_summary|rtm|release_notes|sop|user_guide"
  },
  "top_k": 10
}
```

## Custom Document MCP
Capabilities:
- Extract requirements
- Parse uploaded files
- Identify tables and sections
- Generate structured requirement objects

Inputs:
```json
{
  "s3_uri": "s3://bucket/path/file.pdf",
  "document_type": "rfp|validation_package|release_note|unknown"
}
```
