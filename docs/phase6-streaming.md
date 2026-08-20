# Phase 6: Streaming (Server-Sent Events) Specification

## Architecture Overview

```text
Client Application (Python / JS / Curl / Mobile)
                   │
                   ▼ (POST /api/v1/chat/stream)
              API Gateway
                   │
                   ▼ (SSE Proxy Stream)
              Chat Service
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
StreamManager          LLMStreamClient
(Buffer & Events)      (Mock/Ollama/OpenAI)
       │                       │
       └───────────┬───────────┘
                   ▼
       Typed Event Bus (SSE)
       [status, token, source, tool, done]
```

## Implemented Event Types

| Event Type | Purpose | Payload |
| :--- | :--- | :--- |
| `status` | Lifecycle state | `status`, `message` |
| `token` | Incremental LLM text chunk | `content`, `token_index` |
| `source` | Citation for RAG context | `document_id`, `source`, `page`, `relevance_score` |
| `tool_start` | Tool call initiation | `tool_name`, `arguments` |
| `tool_result` | Tool execution output | `tool_name`, `status`, `result`, `error` |
| `error` | Failure report | `code`, `message` |
| `done` | Stream completion | `message_id`, `conversation_id`, `usage`, `model` |

## Endpoints Created
- **API Gateway**: `POST /api/v1/chat/stream`
- **Chat Service**: `POST /api/v1/chat/stream`
