# Phase 3: Conversation Memory Specification

## Architectural Overview

```text
                    Chat Service
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
            Redis     PostgreSQL    LLM
              │          │          │
          Recent       Permanent    Generate
          context       history
```

### PostgreSQL Schema
- `users`: `id`, `external_id`, `created_at`
- `conversations`: `id`, `user_id`, `title`, `created_at`, `updated_at`
- `messages`: `id`, `conversation_id`, `role`, `content`, `model`, `created_at`

### Redis Caching Strategy
- Key pattern: `conversation:{conversation_id}:recent`
- Data structure: Redis List containing recent messages with a 24-hour expiration (`TTL = 86400s`).
