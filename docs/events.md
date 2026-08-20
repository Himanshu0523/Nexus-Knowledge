# Phase 8: Event Contract Reference

## Topics

| Topic                      | Producer      | Consumers                                    | Partition Key     |
| :------------------------- | :------------ | :------------------------------------------- | :---------------- |
| `chat.message.created`     | chat-service  | audit-group, moderation-group                | `conversation_id` |
| `chat.response.completed`  | chat-service  | audit-group, analytics-group                 | `conversation_id` |
| `chat.response.failed`     | chat-service  | audit-group                                  | `conversation_id` |
| `chat.tool.executed`       | chat-service  | analytics-group                              | `conversation_id` |
| `document.ingested`        | chat-service  | analytics-group                              | `document_id`     |
| `document.deleted`         | chat-service  | audit-group                                  | `document_id`     |

---

## Standard Event Envelope

```json
{
  "event_id":       "evt_abc123",
  "event_type":     "chat.response.completed",
  "version":        1,
  "timestamp":      "2026-08-18T13:00:00+00:00",
  "tenant_id":      "tenant_001",
  "producer":       "chat-service",
  "correlation_id": null,
  "data": { }
}
```

---

## chat.message.created — data payload

```json
{
  "conversation_id": "conv_123",
  "message_id":      "msg_456",
  "user_message":    "Explain machine learning",
  "user_id":         "usr_99"
}
```

## chat.response.completed — data payload

```json
{
  "conversation_id": "conv_123",
  "message_id":      "msg_456",
  "model":           "qwen",
  "input_tokens":    45,
  "output_tokens":   120,
  "latency_ms":      840.0,
  "rag_used":        false
}
```

## chat.response.failed — data payload

```json
{
  "conversation_id": "conv_123",
  "error_code":      "LLM_TIMEOUT",
  "error_message":   "LLM call timed out after 30s"
}
```
