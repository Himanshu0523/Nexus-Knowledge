# Nexus Knowledge — Enterprise Architecture & System Specification

## Architectural Overview

Nexus Knowledge is an enterprise-grade conversational AI platform built on an **Agentic, Self-Healing Enterprise Mesh**. It transitions beyond basic single-pass RAG into an autonomous, event-driven microservices architecture.

```text
Phase 1  → Canonical API Contract
Phase 2  → Decoupled Multi-Provider LLM Gateway
Phase 3  → Multi-Tier Conversation Memory (Redis + PostgreSQL)
Phase 4  → Hierarchical Graph RAG & Hybrid Search (RRF)
Phase 5  → Sandboxed Agent Runtime & Autonomous Tools
Phase 6  → Server-Sent Events (SSE) Streaming
Phase 7  → Multi-Language SDKs (Python, TypeScript, Go, Java, C++)
Phase 8  → Event-Driven Kafka Backbone (Audit, Analytics, Moderation)
Phase 9  → Zero-Trust Security & Multi-Tenant Isolation
Phase 10 → Production Observability, High Availability & Chaos Resilience
Phase 11 → Multi-Agent Collaborative Mesh Routing (Security, SQL, Graph Agents)
Phase 12 → Corrective RAG (CRAG) & Self-Correction Feedback Loops
Phase 13 → Real-Time AI Governance & Proactive Budget Guards
```

---

## Central Core: Agentic Enterprise Mesh

```text
                             Client Applications
                     (React / Vite SSE Stream, Native SDKs)
                                      │
                                      ▼
                             API Gateway (:8000)
                     ├─ Telemetry & Tracing (OTel)
                     ├─ Idempotency Cache (Redis)
                     ├─ Strict Rate Limiting (Token Bucket)
                     └─ JWT Authentication & Tenant Context Injection
                                      │
                                      ▼
                        Enterprise Mesh Router
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
Security/Compliance Agent      SQL/Analytics Agent          Graph RAG Synthesis Agent
 (PII Scrubbing & Boundaries) (PostgreSQL Metrics & Spend)  (Hybrid RRF + Graph Traversal)
        │                             │                             │
        └─────────────────────────────┼─────────────────────────────┘
                                      ▼
                       Chat Orchestrator (v3.1.0)
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
       Memory                   Advanced RAG                Agent Tools
 (Redis + PostgreSQL)      (Qdrant + BM25 + NetworkX)      (Sandboxed Python)
          │                           │                           │
          │                   Corrective RAG (CRAG)               │
          │               (Grading, Rewriting, Fallback)          │
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      ▼
                          LLM Gateway & Failover
                          (Ollama / OpenAI / Claude)
                                      │
                                      ▼
                         Kafka Event Distribution
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
      Audit Service           Analytics Service         Moderation Service
    (Compliance Trails)    (Tokens, Budget Alerts)     (Safety & Toxicity)
```

---

## Component Deep Dive

### 1. Edge & API Gateway Layer (`api-gateway/`)
* **Technology:** FastAPI, Redis, OpenTelemetry, Prometheus.
* **Responsibilities:**
  * JWT validation and tenant context (`tenant_id`) injection into downstream headers.
  * Distributed token-bucket rate limiting per tenant tier.
  * Redis-backed idempotency key deduplication.
  * Persistent SSE streaming termination back to clients.

### 2. Multi-Agent Mesh Routing (`services/chat-service/src/agent_runtime/mesh_router.py`)
* Routes incoming queries to specialized autonomous worker agents:
  * **SecurityComplianceAgent:** Scans for PII (SSN, credit card, API keys) and enforces zero cross-tenant data bleed.
  * **SQLAnalyticsAgent:** Directly answers structured telemetry, token consumption, and graph topology queries.
  * **GraphRAGSynthesisAgent:** Handles document grounding, multi-hop knowledge graph queries, and CRAG self-correction.

### 3. Hierarchical Graph RAG & Hybrid Retrieval (`services/chat-service/src/rag/`)
* **Dense + Sparse Hybrid Search:** Fuses Qdrant dense vector search with BM25Okapi lexical retrieval using Reciprocal Rank Fusion ($k=60$).
* **Cross-Encoder Neural Reranking:** Re-scores top-20 retrieved candidates using `sentence_transformers.CrossEncoder` (`ms-marco-MiniLM-L-6-v2`) with sigmoid-normalized scores.
* **NetworkX Knowledge Graph:** Extracts semantic relation triples (`DEPENDS_ON`, `REGULATES`, `PROVIDES`, `CONTAINS`) and performs multi-hop traversal to resolve complex cross-document dependencies.

### 4. Corrective RAG (CRAG) Self-Correction Loop (`services/chat-service/src/rag/crag.py`)
* Evaluates retrieved context before prompt construction:
  * **CORRECT ($\ge 0.75$):** Passes verified chunks directly to synthesis.
  * **AMBIGUOUS ($0.40 - 0.74$):** Decomposes conversational queries into core keywords and executes a secondary hybrid retrieval pass.
  * **INCORRECT ($< 0.40$):** Eliminates hallucinations via explicit guardrail advisories and safe external fallbacks.

### 5. Real-Time Token Cost Attribution & Budget Guards (`shared/governance/`)
* Tracks exact token usage and USD cost per tenant against tier policies (Starter, Pro, Enterprise).
* Proactive **80% Budget Warning Threshold** and **100% Hard Quota Limit**.
* Publishes asynchronous Kafka events on `analytics.budget.alert`.

---

## Verification & Test Suite

The Agentic Mesh is validated by automated integration tests:
* Test suite: `tests/test_agentic_mesh.py`
* Run: `python tests/test_agentic_mesh.py`
* Result: 6/6 test cases passing (`OK`).
