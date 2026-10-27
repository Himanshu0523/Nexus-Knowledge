# Nexus Knowledge: Agentic, Self-Healing Enterprise Mesh

Nexus Knowledge transitions beyond basic RAG pipelines (`Query -> Retrieve Chunks -> LLM -> Answer`) into a production-grade **Agentic, Self-Healing Enterprise Mesh**.

---

## 1. High-Level Architecture Overview

```
                                 [ Client Applications ]
                         (React / Vite SSE Stream, Python / TS SDKs)
                                            │
                                            ▼ (HTTPS / JWT Auth)
                                 [ API Gateway Layer ]
                            (Tenant Context Injection, Token Bucket)
                                            │
               ┌────────────────────────────┼───────────────────────────┐
               ▼                            ▼                           ▼
    [ Multi-Agent Mesh Router ]   [ Ingestion Pipeline ]      [ Governance & Auditing ]
               │                            │                           │
  ┌────────────┼───────────┐                ├─► PII Sanitization        ├─► Real-time Token Attribution
  │            │           │                ├─► BM25 Sparse Index       ├─► 80% & 100% Budget Guards
  ▼            ▼           ▼                ├─► Qdrant Vector DB        └─► Kafka `analytics.budget.alert`
[Security]   [SQL/Data] [Graph RAG]         └─► NetworkX Knowledge Graph
  Agent       Agent       Agent
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
    [ Hybrid Search (RRF) ]   [ Hierarchical Graph RAG ]
    (Qdrant + BM25 Fusion)   (Multi-Hop Entity Traversal)
             │                           │
             └─────────────┬─────────────┘
                           ▼
              [ Cross-Encoder Reranker ]
            (ms-marco-MiniLM Neural Scoring)
                           │
                           ▼
          [ Corrective RAG (CRAG) Evaluator ]
          ├─► High Confidence (>= 0.75): Pass through
          ├─► Ambiguous (0.40 - 0.74): Query Reformulation & Secondary Pass
          └─► Low Confidence (< 0.40): Guardrail Safe Fallback
                           │
                           ▼
          [ LLM Synthesis & Streaming Engine ]
```

---

## 2. Core Architectural Pillars

### Pillar 1: Hierarchical Graph RAG (Replacing Flat Vector Search)
* **File:** `services/chat-service/src/rag/graph_rag.py`
* **Technology:** NetworkX directed multigraphs, isolated per tenant (`tenant_id`).
* **Concept:** Flat vector search fails on holistic, multi-document enterprise questions (e.g., *"How do security protocols impact API gateway rate limits across all tenants?"*).
* **Implementation:**
  * **Entity Extraction:** Mines domain concepts, protocols, technical identifiers, and acronyms from documents during chunking.
  * **Relation Mining:** Extracts semantic triples (`(Subject) --[RELATION]--> (Object)`: e.g. `DEPENDS_ON`, `REGULATES`, `PROVIDES`, `CONTAINS`).
  * **Multi-Hop Traversal:** Executes `ego_graph` and shortest-path pathfinding to discover cross-document semantic dependencies and passes graph summaries to the LLM.

### Pillar 2: Hybrid Search with Reciprocal Rank Fusion (RRF)
* **File:** `services/chat-service/src/rag/retriever.py`
* **Formula:**
  $$RRF(d) = \frac{w_{\text{dense}}}{k + \text{rank}_{\text{dense}}(d)} + \frac{w_{\text{sparse}}}{k + \text{rank}_{\text{sparse}}(d)}$$
  where $k=60$, $w_{\text{dense}}=0.6$, $w_{\text{sparse}}=0.4$.
* **Why it beats others:** Pure vector search frequently misses exact alphanumeric strings (e.g. error code `ERR_AUTH_GATEWAY_401`, tenant UUIDs, API keys). Blending BM25Okapi lexical retrieval with Qdrant dense vector embeddings guarantees exact keyword precision alongside conceptual semantics.

### Pillar 3: Cross-Encoder Reranking
* **File:** `services/chat-service/src/rag/reranker.py`
* **Technology:** `cross-encoder/ms-marco-MiniLM-L-6-v2` with deep bi-encoder fallback.
* **Implementation:** Top 20 retrieved candidates are evaluated as query-document pairs through a cross-attention transformer, outputting sigmoid-normalized $[0.0, 1.0]$ confidence scores to filter out context noise before prompt generation.

### Pillar 4: Corrective RAG (CRAG) & Self-Correction Evaluation Loop
* **File:** `services/chat-service/src/rag/crag.py`
* **Automated Decision State Machine:**
  * **CORRECT ($\ge 0.75$ confidence):** Context is strictly verified; filtered top chunks pass directly to synthesis.
  * **AMBIGUOUS ($0.40 - 0.74$ confidence):** Automated query decomposition and keyword expansion triggers a secondary targeted hybrid retrieval pass to retrieve missing ground truth.
  * **INCORRECT ($< 0.40$ confidence):** Knowledge base does not contain the required ground truth. The system triggers an external fallback and explicitly refuses to hallucinate, citing an anti-hallucination guardrail alert.

### Pillar 5: Multi-Agent Collaborative Mesh Routing
* **File:** `services/chat-service/src/agent_runtime/mesh_router.py`
* **Autonomous Micro-Agents:**
  * **SecurityComplianceAgent:** Performs zero-trust PII inspection (SSN, credit card, API keys) and enforces cross-tenant data bleed boundaries.
  * **SQLAnalyticsAgent:** Directly queries PostgreSQL tenant telemetry, token consumption, and graph topology stats.
  * **GraphRAGSynthesisAgent:** Orchestrates end-to-end Hybrid RRF, Graph RAG traversal, and CRAG self-correction.
  * **EnterpriseMeshRouter:** Evaluates prompt intent and dynamically dispatches tasks across specialized agents.

### Pillar 6: Real-Time Token Cost Attribution & Budget Guards
* **Files:** `shared/governance/spend_tracker.py`, `shared/events/chat.py`, `services/analytics-service/src/consumer.py`
* **Enterprise Guardrails:**
  * Real-time dollar and token consumption tracking per tenant.
  * Proactive **80% Budget Warning Threshold** and **100% Hard Quota Enforcement**.
  * Asynchronous Kafka event publishing on topic `analytics.budget.alert`.

---

## 3. Verification & Test Suite

The entire Agentic Mesh is covered by automated integration tests:
* **Test file:** `tests/test_agentic_mesh.py`
* **Command:** `python tests/test_agentic_mesh.py`
* **Test Coverage:**
  1. `test_01_hierarchical_graph_rag_extraction_and_traversal` (PASSED)
  2. `test_02_hybrid_search_rrf_blending` (PASSED)
  3. `test_03_cross_encoder_and_semantic_reranking` (PASSED)
  4. `test_04_corrective_rag_crag_evaluator_and_query_reformulation` (PASSED)
  5. `test_05_multi_agent_collaborative_mesh_router` (PASSED)
  6. `test_06_realtime_token_attribution_and_budget_guards` (PASSED)
