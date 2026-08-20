# Canonical API Contract Specification

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000/api/v1`

---

## 1. Authentication
Clients authenticate by passing an API key in HTTP headers:
- `X-API-Key: <YOUR_API_KEY>` or
- `Authorization: Bearer <YOUR_API_KEY>`

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
  "message": "Explain quantum computing",
  "knowledge_base_id": "kb_doc_1",
  "metadata": {
    "user_id": "usr_99",
    "tenant_id": "tenant_default"
  }
}
```

#### Response (200 OK)
```json
{
  "conversation_id": "conv_12345",
  "message_id": "msg_abc123",
  "response": "Quantum computing uses qubits...",
  "sources": [
    {
      "document": "quantum_intro.pdf",
      "page": 1,
      "relevance_score": 0.92
    }
  ],
  "usage": {
    "input_tokens": 45,
    "output_tokens": 120
  },
  "model": "qwen"
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
`data: {"type": "<EVENT_TYPE>", "timestamp": 1700000000.0, "event_id": "evt_123", ...}`

#### Supported Event Types
1. **`status`**: Lifecycle stage update (`started`, `processing`, `retrieving`, `generating`, `completed`)
2. **`source`**: RAG citation source document
3. **`token`**: Incremental token payload content
4. **`tool_start`**: Execution start of external tool
5. **`tool_result`**: Outcome of executed tool
6. **`error`**: Processing error detail
7. **`done`**: Final event containing `message_id`, `usage`, and completion state

---

### 2.3 Document Ingestion API
- **`POST /documents`**: Upload binary file (`multipart/form-data`) with parameters `file`, `document_id`, `tenant_id`.
- **`GET /documents/{document_id}/status`**: Query processing status.
- **`DELETE /documents/{document_id}`**: Purge vector chunks.

---

### 2.4 Conversation History API
- **`GET /conversations/{conversation_id}/history`**: Fetch multi-turn message history.
- **`DELETE /conversations/{conversation_id}/cache`**: Purge Redis ephemeral cache.

---

## 3. Error Standard Schema

All API errors return standard HTTP 4xx/5xx status codes with payload:
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Field 'message' cannot be empty",
    "request_id": "req_xyz789"
  }
}
```
