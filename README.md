<div align="center">

# 🤖 Nexus Knowledge

### Enterprise Multi-Tenant Conversational AI Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688?style=for-the-badge&logo=fastapi&logoColor=white)](#)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](#)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)](#)
[![Kafka](https://img.shields.io/badge/Apache_Kafka-7.5.0-231F20?style=for-the-badge&logo=apachekafka&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue?style=for-the-badge&logo=apache&logoColor=white)](./LICENSE)

**Secure, scalable, multi-tenant AI infrastructure built for the enterprise.**

Nexus Knowledge combines Retrieval-Augmented Generation (RAG), autonomous tool execution, and an event-driven microservices architecture to serve fully isolated tenants at scale — without compromising on security, observability, or resilience.

[Architecture](#️-architecture) · [Quick Start](#-quick-start) · [Configuration](#️-configuration) · [Project Structure](#️-project-structure) · [Security](#-security--access-control) · [HA & DR](#️-high-availability--disaster-recovery) · [Production Deployment](#-production-deployment)

</div>

---

## 📋 Table of Contents

- [Architecture](#️-architecture)
- [Quick Start](#-quick-start)
- [Configuration](#️-configuration)
- [Project Structure](#️-project-structure)
- [Security & Access Control](#-security--access-control)
- [High Availability & Disaster Recovery](#️-high-availability--disaster-recovery)
- [Observability](#-observability)
- [Chaos Engineering](#-chaos-engineering)
- [Production Deployment](#-production-deployment)
- [Running Tests](#-running-tests)
- [License](#-license)

---

## 🏗️ Architecture

Nexus Knowledge is a microservices platform. The **API Gateway** (`:8000`) is the single public entry point — it proxies requests to the **Chat Service** after enforcing auth, rate limiting, and idempotency. The Chat Service (version 3.0.0) owns LLM generation, RAG retrieval, and autonomous agent tool execution. All side-effects (audit, analytics, moderation) flow via **Apache Kafka** completely decoupled from the request path.

```mermaid
graph TD
    Client["Web UI / SDKs"] -->|"HTTPS / SSE (port 8000)"| Gateway["API Gateway\n:8000"]

    subgraph Gateway Middleware
        MW1[TelemetryMiddleware]
        MW2[IdempotencyMiddleware]
        MW3[SecurityHeadersMiddleware]
        MW4["CORS / RateLimit / Auth"]
    end

    Gateway --> MW1 --> MW2 --> MW3 --> MW4

    MW4 -->|"Routes: /api/v1/chat\n/api/v1/chat/stream\n/api/v1/documents\n/api/v1/tools"| ChatSvc["Chat Service v3.0.0\n(internal: chatbot-network)"]

    ChatSvc <-->|"Conversation cache\n(Sentinel HA)"| Redis[("Redis 7\n:6379 internal")]
    ChatSvc <-->|"Conversation history\nDocument metadata"| PG[("PostgreSQL 14\n:5432 internal")]
    ChatSvc <-->|"Vector search\n(Cluster HA, RF=2)"| Qdrant[("Qdrant\n:6333/:6334 internal")]
    ChatSvc <-->|"LLM generation\nEmbedding"| LLM["LLM Provider\n(Ollama :11434 / mock)"]

    ChatSvc -->|"Publish events"| Kafka["Apache Kafka\nconfluentinc/cp-kafka:7.5.0\n:9092 host / :29092 internal"]

    Kafka -->|"chat.events\naudit.events"| Audit["Audit Service\n(internal)"]
    Kafka -->|"analytics.events"| Analytics["Analytics Service\n(internal)"]
    Kafka -->|"chat.events"| Moderation["Moderation Service\n(internal)"]
```

### API Gateway — Routes (prefix: `/api/v1`)

| Router module | Mounted at | Description |
|---|---|---|
| `routes/chat.py` | `/api/v1/chat` | Synchronous chat endpoint |
| `routes/chat_stream.py` | `/api/v1/chat/stream` | Streaming SSE chat endpoint |
| `routes/documents.py` | `/api/v1/documents` | Document upload, status, delete |
| `routes/tools.py` | `/api/v1/tools` | Agent tool listing/execution |
| *(telemetry)* | `/metrics`, `/health*` | Prometheus metrics & health probes |

### API Gateway — Middleware Stack (applied in order)

| Middleware | Source | Purpose |
|---|---|---|
| `TelemetryMiddleware` | `shared/telemetry` | Prometheus metrics, OpenTelemetry tracing, request timing |
| `IdempotencyMiddleware` | `shared/security/idempotency.py` | Redis-backed idempotency key deduplication |
| `SecurityHeadersMiddleware` | `api-gateway/src/middleware/security_headers.py` | HSTS, CSP, X-Frame-Options headers |
| `CORSMiddleware` | FastAPI built-in | CORS from `ALLOWED_ORIGINS` env var |
| `rate_limit_middleware` | `api-gateway/src/middleware/rate_limit.py` | Per-tenant rate limiting |
| `verify_api_key` | `api-gateway/src/middleware/auth.py` | JWT / API-Key authentication |

### Service Map

| Service | Host Port | Docker Source | Version |
|---|---|---|---|
| API Gateway | `8000` | `./api-gateway` | — |
| Chat Service | *(internal only)* | `./services/chat-service` | `3.0.0` |
| Audit Service | *(internal only)* | `./services/audit-service` | — |
| Analytics Service | *(internal only)* | `./services/analytics-service` | — |
| Moderation Service | *(internal only)* | `./services/moderation-service` | — |
| Eval Service | *(internal only)* | `./services/eval-service` | — |

> Only the **API Gateway** is published on the host (`0.0.0.0:8000`). All other services run on the internal `chatbot-network` Docker bridge network and are reachable only through the gateway.

### Infrastructure Services

| Component | Image | Host Port | Internal Port |
|---|---|---|---|
| Apache Kafka | `confluentinc/cp-kafka:7.5.0` | `9092` | `29092` (`PLAINTEXT` inter-broker) |
| Zookeeper | `confluentinc/cp-zookeeper:7.5.0` | — | `2181` |
| PostgreSQL | `postgres:14` | — | `5432` |
| Redis | `redis:7-alpine` | — | `6379` |
| Qdrant | `qdrant/qdrant:latest` | — | `6333` (HTTP), `6334` (gRPC) |

> Kafka listener config: `PLAINTEXT://kafka:29092` (internal service-to-service), `PLAINTEXT_HOST://localhost:9092` (host access). Chat Service connects via `kafka:29092` inside the Docker network.

### Kafka Topics

| Topic | Env Var | Producers | Consumers |
|---|---|---|---|
| `chat.events` | `KAFKA_TOPIC_CHAT_EVENTS` | Chat Service | Audit Service, Moderation Service |
| `audit.events` | `KAFKA_TOPIC_AUDIT_EVENTS` | Chat Service | Audit Service |
| `analytics.events` | `KAFKA_TOPIC_ANALYTICS_EVENTS` | Chat Service | Analytics Service |

---

## 🚀 Quick Start

### Requirements

- Docker & Docker Compose
- Python 3.11+ (for local development only)
- An Ollama-compatible LLM server at `http://localhost:11434` (or leave `LLM_PROVIDER=mock` in `.env` — the default)

### 1 · Configure Environment

```bash
cp .env.example .env
# Edit .env — at minimum change:
#   POSTGRES_PASSWORD, JWT_SECRET, API_KEY_SALT
```

### 2 · Start Infrastructure

```bash
docker-compose up -d postgres redis qdrant zookeeper kafka
```

### 3 · Start All Services

```bash
docker-compose up -d --build
```

### 4 · Verify Health

```bash
# API Gateway is the only service published on the host
curl http://localhost:8000/health
```

### Local Development (without Docker)

Run services individually in separate terminals. Infrastructure (PostgreSQL, Redis, Qdrant, Kafka) must still be running via Docker.

```bash
# Terminal 1 — API Gateway (port 8000)
cd api-gateway
pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Terminal 2 — Chat Service (port 8001)
cd services/chat-service
pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
```

### Web UI

```bash
cd frontend
python -m http.server 3000
# → http://localhost:3000
```

---

## ⚙️ Configuration

All settings are driven by environment variables. Copy `.env.example` to `.env` and adjust. The full variable list with all defaults is in [`.env.example`](.env.example).

### Key Variables

| Variable | Default (`.env.example`) | Description |
|---|---|---|
| `APP_NAME` | `Chatbot Platform` | Application name |
| `APP_ENV` | `development` | `development` or `production` |
| `DEBUG` | `true` | Enable debug mode |
| `VERSION` | `1.0.0` | Application version |
| `LOG_LEVEL` | `INFO` | Python log level |
| `API_PREFIX` | `/api/v1` | API route prefix |
| `PORT` | `8000` | Gateway listen port |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `chatbot_db` | Database name |
| `POSTGRES_USER` | `chatbot` | DB user |
| `POSTGRES_PASSWORD` | `change-me-in-production` | DB password — **must be changed** |
| `POSTGRES_POOL_SIZE` | `20` | Connection pool size |
| `POSTGRES_MAX_OVERFLOW` | `40` | Max overflow connections |
| `DATABASE_URL` | `postgresql://chatbot:...@localhost:5432/chatbot_db` | Full DB connection URL |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database index |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_MAX_CONNECTIONS` | `50` | Redis connection pool size |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant HTTP port |
| `QDRANT_GRPC_PORT` | `6334` | Qdrant gRPC port |
| `QDRANT_COLLECTION` | `document_chunks` | Vector collection name |
| `KAFKA_BROKERS` | `localhost:9092` | Kafka bootstrap servers |
| `KAFKA_CONSUMER_GROUP` | `chatbot-consumers` | Consumer group ID |
| `KAFKA_TOPIC_CHAT_EVENTS` | `chat.events` | Chat event topic |
| `KAFKA_TOPIC_AUDIT_EVENTS` | `audit.events` | Audit event topic |
| `KAFKA_TOPIC_ANALYTICS_EVENTS` | `analytics.events` | Analytics event topic |
| `LLM_PROVIDER` | `mock` | `mock`, `ollama`, or `openai` |
| `LLM_MODEL` | `qwen` | Model identifier |
| `LLM_BASE_URL` | `http://localhost:11434` | Ollama / LLM API base URL |
| `LLM_MAX_TOKENS` | `2000` | Max tokens per generation |
| `LLM_TEMPERATURE` | `0.7` | Sampling temperature |
| `LLM_TIMEOUT` | `30` | Request timeout (seconds) |
| `EMBEDDING_MODEL` | `mock` | Embedding backend |
| `EMBEDDING_DIM` | `384` | Embedding vector dimension |
| `JWT_SECRET` | `change-me-in-production-use-a-long-random-string` | HS256 signing secret — **must be changed** |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRY` | `3600` | Access token TTL (seconds) |
| `JWT_REFRESH_TOKEN_EXPIRY` | `2592000` | Refresh token TTL (seconds, 30 days) |
| `API_KEY_SALT` | `change-me-in-production` | API key bcrypt salt — **must be changed** |
| `API_KEY_PREFIX` | `cb_live_` | Live API key prefix |
| `API_KEY_TEST_PREFIX` | `cb_test_` | Test API key prefix |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_REQUESTS` | `100` | Global rate limit (req / window) |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window (seconds) |
| `RATE_LIMIT_CHAT_REQUESTS` | `60` | Chat endpoint rate limit |
| `RATE_LIMIT_DOCUMENTS_REQUESTS` | `10` | Document upload rate limit |
| `RATE_LIMIT_STREAM_REQUESTS` | `20` | SSE stream rate limit |
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus endpoint |
| `GRAFANA_URL` | `http://localhost:3000` | Grafana URL |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OpenTelemetry OTLP endpoint |
| `ENABLE_TRACING` | `true` | Enable distributed tracing |
| `ENABLE_METRICS` | `true` | Enable Prometheus metrics |
| `KUBERNETES_NAMESPACE` | `chatbot-platform` | K8s namespace for all resources |
| `API_GATEWAY_URL` | `http://localhost:8000` | API Gateway service URL |
| `CHAT_SERVICE_URL` | `http://localhost:8001` | Chat Service URL |
| `AUDIT_SERVICE_URL` | `http://localhost:8002` | Audit Service URL |
| `ANALYTICS_SERVICE_URL` | `http://localhost:8003` | Analytics Service URL |
| `MODERATION_SERVICE_URL` | `http://localhost:8004` | Moderation Service URL |

> **Production rule:** Change all `change-me-in-production` values before any deployment. Inject secrets via Kubernetes `Secret` objects or a vault solution — never commit `.env` to version control.

---

## 🛠️ Project Structure

```text
ChatBots_platform/
├── api-gateway/                    # Ingress, JWT/API-Key auth, RBAC, rate limiting
├── services/
│   ├── chat-service/               # LLM engine, RAG pipeline, agent tool execution
│   ├── audit-service/              # Kafka consumer — compliance logging
│   ├── analytics-service/          # Kafka consumer — tenant usage metrics
│   ├── moderation-service/         # Kafka consumer — PII / toxicity scanning
│   └── eval-service/               # AI evaluation, RAGAS scoring, drift detection
├── shared/
│   ├── chaos/                      # ChaosInjector, FaultType, GameDayDrillRunner
│   ├── dr/                         # Disaster Recovery orchestration module
│   ├── events/                     # Kafka event schemas & publisher
│   ├── governance/                 # PII sanitizer, spend tracker
│   ├── ha/                         # HA routing: db_routing, redis_sentinel, qdrant_ha
│   ├── kafka/                      # Kafka producer / consumer utilities
│   ├── security/                   # CircuitBreaker, IdempotencyMiddleware, request_id
│   └── telemetry/                  # Prometheus metrics, OpenTelemetry tracer, logging
├── infra/
│   ├── chaos/                      # Chaos Mesh CRDs: network-chaos, pod-chaos, stress-chaos
│   ├── dr/
│   │   ├── k8s/                    # DR Kubernetes manifests
│   │   └── scripts/                # postgres_backup.sh, postgres_restore.sh,
│   │                               #   qdrant_snapshot.py, valkey_backup.py
│   ├── k8s/                        # K8s Deployments, HPA, PDB, Ingress, HA manifests
│   ├── kafka/                      # Kafka cluster configuration
│   ├── monitoring/                 # Prometheus & Grafana configuration
│   └── nginx/                      # Nginx ingress config
├── frontend/                       # Web UI (HTML/CSS/JS — zero external dependencies)
├── sdks/                           # Client libraries
├── tests/
│   ├── test_ha_resilience.py       # HA routing & Sentinel failover tests
│   ├── test_dr_failover.py         # DR backup integrity & failover tests
│   └── test_chaos_reliability.py   # ChaosInjector & GameDay drill tests
├── test_phase3.py                  # Phase 3 integration tests (root)
├── test_rag.py                     # RAG pipeline tests (root)
├── test_sdks.py                    # SDK client tests (root)
├── test_security.py                # Security/auth tests (root)
├── test_streaming.py               # SSE streaming tests (root)
├── test_telemetry.py               # Observability/metrics tests (root)
├── docs/                           # Deployment guides, API references
├── scripts/                        # Operational scripts (deploy.sh, etc.)
├── docker-compose.yml
├── .env.example                    # Full environment variable reference
└── .gitignore
```

---

## 🔐 Security & Access Control

Every request passes through the **API Gateway** (`:8000`) before reaching any internal service. The gateway enforces:

- **JWT Authentication** — HS256-signed tokens; 1-hour access TTL (`JWT_ACCESS_TOKEN_EXPIRY=3600`), 30-day refresh TTL (`JWT_REFRESH_TOKEN_EXPIRY=2592000`)
- **API Key Authentication** — prefixed keys (`cb_live_*`, `cb_test_*`) with bcrypt-hashed storage
- **RBAC** — role-based permission checks per endpoint
- **Rate Limiting** — 100 req/60 s global; 60 req/60 s on chat; 20 req/60 s on streaming; 10 req/60 s on document upload
- **Idempotency** — `Idempotency-Key` header support on `POST`/`PUT`/`PATCH` requests (Redis-backed, 24-hour TTL)
- **Circuit Breaker** — automatic `OPEN → HALF_OPEN → CLOSED` state machine on downstream failures (`shared/security/circuit_breaker.py`)
- **PII Sanitization** — all AI outputs scrubbed by `shared/governance/pii_sanitizer.py` before storage
- **CORS** — configurable via `ALLOWED_ORIGINS` (default `*`; restrict in production)

> **Never commit real secrets.** Use `.env` (git-ignored) locally. In production, inject secrets via Kubernetes `Secret` objects or a secrets manager.

---

## 🏛️ High Availability & Disaster Recovery

### HA Components (`shared/ha/`)

| Module | Class | Strategy |
|---|---|---|
| `db_routing.py` | `HARoutedDatabasePool` | Write → Primary; Read → round-robin healthy replicas; fallback to Primary |
| `redis_sentinel.py` | `HASentinelRedisClient` | Sentinel-discovered master for writes; replica for reads; auto-reconnect on failover |
| `qdrant_ha.py` | `HAQdrantClusterClient` | Active-node cycling across cluster (modulo-bounded); degraded node exclusion; replication factor: 2 |

### Kubernetes HA Manifests (`infra/k8s/`)

| Manifest | What it deploys |
|---|---|
| `namespace.yaml` | `chatbot-platform` namespace |
| `api-gateway-ha.yaml` | API Gateway — 3 replicas, pod anti-affinity, liveness/readiness probes |
| `chat-service-ha.yaml` | Chat Service — 3 replicas, rolling update strategy |
| `postgres-ha.yaml` | PostgreSQL primary + read replica StatefulSets |
| `valkey-sentinel-ha.yaml` | Valkey / Redis Sentinel cluster |
| `qdrant-cluster.yaml` | Qdrant vector DB cluster (replication factor 2) |
| `kafka-cluster.yaml` | Kafka broker cluster |
| `hpa-autoscaling.yaml` | Horizontal Pod Autoscaler for gateway & chat-service |
| `pod-disruption-budgets.yaml` | PDB ensuring minimum availability during node drain |
| `ingress.yaml` | Ingress routing rules |

### Disaster Recovery Scripts (`infra/dr/scripts/`)

| Script | Purpose |
|---|---|
| `postgres_backup.sh` | `pg_dump` → gzip compression → SHA256 checksum → S3 upload |
| `postgres_restore.sh` | Checksum-verified restore from S3 backup |
| `qdrant_snapshot.py` | Qdrant collection snapshot with SHA256 integrity verification |
| `valkey_backup.py` | Redis/Valkey `BGSAVE` RDB dump with checksum packaging |

---

## 📊 Observability

Nexus uses a three-pillar observability stack implemented in `shared/telemetry/`:

| Signal | Implementation | Endpoint / Sink |
|---|---|---|
| **Metrics** | `MetricsCollector` — Prometheus text format | `GET /metrics` on each service |
| **Traces** | OpenTelemetry `TracingMiddleware` → OTLP exporter | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| **Logs** | Structured JSON with `trace_id` & `tenant_id` correlation | stdout / log aggregator |

### Prometheus Metrics Tracked

- `http_requests_total` — labelled by method, endpoint, status, tenant
- `http_request_duration_seconds` — histogram (P50 / P95 / P99)
- `llm_requests_total` + `llm_tokens_total` — by provider, model, tenant
- `rag_operations_total` + `rag_operation_duration_seconds`
- `db_operations_total` + `db_operation_duration_seconds`
- `kafka_messages_total` + `kafka_consumer_lag`
- `tool_calls_total` + `tool_call_duration_seconds`
- `tenant_requests_total` + `tenant_tokens_total`

---

## 🔥 Chaos Engineering

A production-grade chaos engineering framework is implemented under `shared/chaos/` with two modules: `injector.py` (fault injection engine) and `gameday_runner.py` (orchestrated drill execution).

### `FaultType` Enum (`shared/chaos/injector.py`)

| Fault | Value | Effect |
|---|---|---|
| `NETWORK_LATENCY` | `network_latency` | Inject configurable ms delay into service path |
| `PACKET_LOSS` | `packet_loss` | Simulate packet loss rate |
| `PROCESS_CRASH` | `process_crash` | Kill target process |
| `SERVICE_DEGRADATION` | `service_degradation` | CPU/memory throttling simulation |
| `CACHE_EVICTION` | `cache_eviction` | Flush Redis/Valkey cache keys |
| `LLM_PROVIDER_OUTAGE` | `llm_provider_outage` | Simulate LLM API failure at configured rate |
| `DATABASE_FAILOVER` | `database_failover` | Trigger simulated DB primary crash & replica promotion |

### `SafetyPolicy` Defaults (`shared/chaos/injector.py`)

| Parameter | Default | Description |
|---|---|---|
| `max_error_rate_pct` | `5.0` | Auto-abort if error rate exceeds 5% |
| `max_latency_p99_ms` | `2000.0` | Auto-abort if P99 latency exceeds 2000 ms |
| `auto_rollback` | `True` | Automatically roll back on SLA breach |
| `max_duration_seconds` | `60` | Hard cap on experiment duration |

### Chaos Mesh Schedules (`infra/chaos/`)

| Manifest | Schedule | Target & Effect |
|---|---|---|
| `network-chaos.yaml` | Weekly (Sunday 03:00 UTC) | `chat-service` → `api-gateway` 300 ms latency injection |
| `pod-chaos.yaml` | Weekly (Sunday 03:30 UTC) | `chat-service` pod-kill weekly drill |
| `stress-chaos.yaml` | One-shot | `chat-service` CPU 80% + `api-gateway` memory 512 MB |

### Running a GameDay Drill

```python
from shared.chaos import GameDayDrillRunner

runner = GameDayDrillRunner()
scenarios = runner.create_standard_enterprise_scenarios()
scorecard = await runner.execute_drill(scenarios[0])
print(scorecard.to_markdown())
```

---

## 🚢 Production Deployment

Nexus Knowledge deploys to Kubernetes in the `chatbot-platform` namespace (defined in `infra/k8s/namespace.yaml`).

```bash
# 1. Create namespace
kubectl apply -f infra/k8s/namespace.yaml

# 2. Deploy stateful infrastructure
kubectl apply -f infra/k8s/kafka-cluster.yaml
kubectl apply -f infra/k8s/postgres-ha.yaml
kubectl apply -f infra/k8s/valkey-sentinel-ha.yaml
kubectl apply -f infra/k8s/qdrant-cluster.yaml

# 3. Deploy application services (HA replicas)
kubectl apply -f infra/k8s/api-gateway-ha.yaml
kubectl apply -f infra/k8s/chat-service-ha.yaml

# 4. Apply autoscaling & availability policies
kubectl apply -f infra/k8s/hpa-autoscaling.yaml
kubectl apply -f infra/k8s/pod-disruption-budgets.yaml

# 5. Apply ingress
kubectl apply -f infra/k8s/ingress.yaml
```

Or use the automated deployment script:

```bash
./scripts/deploy.sh production
```
---

## 🧪 Running Tests

```bash
# HA resilience — db routing, sentinel failover, Qdrant cluster HA
pytest tests/test_ha_resilience.py -v

# Disaster Recovery — backup integrity & failover verification
pytest tests/test_dr_failover.py -v

# Chaos Engineering & Reliability — ChaosInjector, GameDay drills
pytest tests/test_chaos_reliability.py -v -s

# Integration & Component tests (root level)
pytest test_phase3.py test_rag.py test_sdks.py test_security.py test_telemetry.py -v
```

---

## 📜 License

Copyright 2024 Nexus Knowledge Contributors

Licensed under the **Apache License, Version 2.0** — you may use, modify, and distribute this software freely, including for commercial purposes, under the terms of the license.

See the full license text in [`LICENSE`](./LICENSE) or at [apache.org/licenses/LICENSE-2.0](https://www.apache.org/licenses/LICENSE-2.0).

> **Why Apache 2.0?**  
> Apache 2.0 includes an explicit **patent grant**, protecting contributors and users from patent claims. It is permissive for enterprise adoption, compatible with most open-source ecosystems, and is the standard for production-grade infrastructure projects (Kubernetes, Kafka, Airflow, FastAPI all use it).

<div align="center">

Built for teams that need AI at enterprise scale. **Open source, open collaboration.**

</div>
