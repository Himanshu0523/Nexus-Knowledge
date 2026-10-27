# Canonical API Contract Specification

**Version:** 3.1.0  
**Base URL:** `http://localhost:8000/api/v1`

---

## 1. Authentication & Multi-Tenancy
Clients authenticate by passing an API key in HTTP headers:
- `X-API-Key: <YOUR_API_KEY>` or
- `Authorization: Bearer <YOUR_API_KEY>`

Tenants are strictly isolated. The tenant identifier is extracted from the JWT token or request metadata (`tenant_id`). All vector operations, knowledge graphs, SQL queries, and spend quotas are sandboxed per tenant.

---

## 2. API Endpoints

### 2.1 Chat Endpoint (Synchronous)
- **Method:** `POST`
- **Path:** `/chat`
- **Content-Type:** `application/json`

#### Request Body
```json
{
  "conversation_id": "conv_12345",
  "message": "How do our security protocols regulate API gateway rate limits?",
  "knowledge_base_id": "kb_doc_1",
  "metadata": {
    "user_id": "usr_99",
    "tenant_id": "tenant_enterprise_demo"
  }
}
```

#### Response (200 OK — Augmented with Graph RAG & CRAG)
```json
{
  "conversation_id": "conv_12345",
  "message_id": "msg_abc123",
  "response": "According to enterprise documentation and the knowledge graph, security protocols regulate rate limits...",
  "sources": [
    {
      "document": "cloud_security_whitepaper.pdf",
      "page": 1,
      "relevance_score": 0.94,
      "chunk_id": "chunk_01"
    }
  ],
  "usage": {
    "input_tokens": 45,
    "output_tokens": 120,
    "cost_usd": 0.00031
  },
  "model": "qwen",
  "graph_rag": {
    "entities": ["Security Protocols", "API Gateway", "Rate Limits"],
    "triples": [
      {
        "subject": "Security Protocols",
        "predicate": "REGULATES",
        "object": "API Gateway"
      }
    ],
    "connected_documents": ["cloud_security_whitepaper.pdf"]
  },
  "crag": {
    "crag_action": "correct",
    "confidence_score": 0.92,
    "chunks_count": 3,
    "reformulated_query": null,
    "fallback_used": false,
    "system_advisory": null
  },
  "analytics_data": null
}
```

#### SQL Analytics Request & Response (Multi-Agent Routing)
When an analytical query is sent (e.g. `"What is our total token consumption and spend?"`), the **Enterprise Mesh Router** dispatches the query directly to the `SQLAnalyticsAgent`:
```json
{
  "conversation_id": "conv_analytics_01",
  "message_id": "msg_sql987",
  "response": "### Tenant Analytics (tenant_enterprise_demo):\n- **Total Tokens Consumed:** 85,000\n- **Input Tokens:** 80,000\n- **Output Tokens:** 5,000\n- **Total Spend (USD):** $0.0750\n- **Total Requests:** 12",
  "sources": [],
  "usage": {
    "input_tokens": 10,
    "output_tokens": 40,
    "cost_usd": 0.0
  },
  "model": "sql-analytics-agent",
  "analytics_data": {
    "tenant_id": "tenant_enterprise_demo",
    "total_tokens": 85000,
    "total_cost_usd": 0.075
  }
}
```

---

### 2.2 Chat Stream Endpoint (Server-Sent Events)
- **Method:** `POST`
- **Path:** `/chat/stream`
- **Content-Type:** `application/json`
- **Response Format:** `text/event-stream`

#### Stream Event Structure
Each event is formatted as standard SSE:
```text
data: {"type": "<EVENT_TYPE>", "timestamp": 1700000000.0, "event_id": "evt_123", ...}\n\n
```

#### Supported Event Types
1. **`status`**: Lifecycle stage updates:
   - `processing` ("Processing request...")
   - `retrieving` ("Traversing Knowledge Graph & Hybrid RRF...")
   - `processing` ("CRAG Self-Correction: Query reformulated to '...'")
   - `generating` ("Generating response...")
2. **`source`**: RAG citation source document with page and confidence.
3. **`token`**: Incremental token payload content (`{"content": "..."}`).
4. **`metadata`**: Diagnostic metadata payloads containing `graph_rag` entity relations and `crag` self-correction diagnostics.
5. **`tool_start`**: Execution start of external agent tool.
6. **`tool_result`**: Outcome of executed agent tool.
7. **`error`**: Processing error detail.
8. **`done`**: Final event containing `message_id`, `usage` (with exact USD cost), and completion state.

---

### 2.3 Document Ingestion API
- **`POST /documents`**: Upload binary file (`multipart/form-data`) with parameters `file`, `document_id`, `tenant_id`.
  - Automatically parses PDF, DOCX, TXT.
  - Generates dense vectors for Qdrant.
  - Builds BM25 sparse index for Hybrid RRF.
  - Extracts entities and semantic triples for Hierarchical Graph RAG.
- **`GET /documents/{document_id}/status`**: Query processing status, vector count, and graph entities/triples mined.
- **`DELETE /documents/{document_id}`**: Purge vector chunks and graph nodes.

---

### 2.4 Conversation History API
- **`GET /conversations/{conversation_id}/history`**: Fetch multi-turn message history.
- **`DELETE /conversations/{conversation_id}/cache`**: Purge Redis ephemeral cache.

---

## 3. Error & Governance Standard Schema

All API errors return standard HTTP 4xx/5xx status codes with payload:
```json
{
  "error": {
    "code": "SPEND_LIMIT_EXCEEDED",
    "message": "Token quota or dollar spend exceeded for tenant 'tenant_abc'. Used: $10.05, Limit: $10.00",
    "request_id": "req_xyz789"
  }
}
```

### Standard Governance Error Codes:
* `MODEL_NOT_ALLOWED`: Model requested is not permitted under tenant plan tier.
* `SPEND_LIMIT_EXCEEDED`: Hard budget cap breached (100% threshold).
* `PII_BLOCKED`: Strict PII policy rejection.
* `CROSS_TENANT_BLEED_BLOCKED`: Cross-tenant data bleed query attempt blocked.
* `TOOL_NOT_ALLOWED`: Autonomous agent tool restricted by tenant policy.
