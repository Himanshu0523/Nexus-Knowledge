# Phase 4: Advanced RAG Specification & Architecture

Nexus Knowledge elevates standard RAG into an **Agentic, Self-Healing Knowledge Mesh** combining **Hierarchical Graph RAG**, **Hybrid Search with Reciprocal Rank Fusion (RRF)**, **Cross-Encoder Neural Reranking**, and **Corrective RAG (CRAG)**.

---

## 1. End-to-End Pipeline Architecture

```text
                     Documents (PDF, DOCX, TXT, MD)
                                   │
                                   ▼
                       Document Parser & Cleaner
                                   │
                                   ▼
                         Semantic Text Chunker
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
Dense Vector Pipeline                               Sparse & Graph Pipeline
 ├─► Dense Transformer Embeddings                    ├─► BM25Okapi Lexical Index
 └─► Qdrant Vector DB (Tenant isolated)             └─► NetworkX Knowledge Graph
                                                          (Entities & Triples)
                                   │
                                   ▼
             Query Pipeline: Hybrid Search & Graph Traversal
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
Dense Vector Candidates                             Sparse Lexical Candidates
 (Qdrant Cosine Similarity)                           (BM25Okapi Exact Terms)
         │                                                   │
         └─────────────────────────┬─────────────────────────┘
                                   ▼
                   Reciprocal Rank Fusion (RRF)
                      RRF(d) = Σ w_i / (k + rank_i)
                                   │
                                   ▼
                 Cross-Encoder Neural Reranker
                 (ms-marco-MiniLM-L-6-v2, Sigmoid [0..1])
                                   │
                                   ▼
                 Hierarchical Graph Traversal
                 (Multi-hop entity ego-graphs & shortest paths)
                                   │
                                   ▼
                 Corrective RAG (CRAG) Evaluator Loop
                 ├─► CORRECT (>= 0.75): Pass through
                 ├─► AMBIGUOUS (0.40 - 0.74): Query Reformulation & Re-retrieval
                 └─► INCORRECT (< 0.40): Guardrail Safe Fallback
                                   │
                                   ▼
                     Grounded LLM Generation
```

---

## 2. Core Modules & Specifications

### 2.1 Ingestion Pipeline ([`ingestion.py`](file:///d:/Python_Ai_Project/ChatBots_platform/services/chat-service/src/rag/ingestion.py))
* **Multi-Format Parsers**: PDF (`pypdf`), Word (`python-docx`), plain text / Markdown.
* **Chunking**: Dynamic sliding-window chunker (500 tokens, 50 overlap) with unicode sanitization.
* **Dual Indexing**:
  1. **Dense Vector Embeddings:** Upserted to Qdrant with payload metadata and strict multi-tenant isolation (`tenant_id`).
  2. **Sparse BM25 Index:** Ingested into `lexical_corpus_index` (`rank-bm25`).
  3. **Knowledge Graph Triples:** Extracted via regex patterns and entity recognizers into tenant-isolated NetworkX multigraphs.

### 2.2 Hybrid Search & Reciprocal Rank Fusion ([`retriever.py`](file:///d:/Python_Ai_Project/ChatBots_platform/services/chat-service/src/rag/retriever.py))
Combines the strengths of semantic vector search and exact term lexical matching:
$$RRF(d) = \frac{w_{\text{dense}}}{k + \text{rank}_{\text{dense}}(d)} + \frac{w_{\text{sparse}}}{k + \text{rank}_{\text{sparse}}(d)}$$
* Parameters: $k=60$, $w_{\text{dense}}=0.6$, $w_{\text{sparse}}=0.4$.
* Prevents vector blindness on exact identifiers (e.g. error code `ERR_AUTH_GATEWAY_401`, tenant UUIDs, technical acronyms like `IaaS`, `JWT`, `RBAC`).

### 2.3 Cross-Encoder Reranking ([`reranker.py`](file:///d:/Python_Ai_Project/ChatBots_platform/services/chat-service/src/rag/reranker.py))
* Evaluates pairs `(query, document_chunk)` using full cross-attention transformer (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
* Normalizes raw logits to $[0.0, 1.0]$ confidence scores using sigmoid activation.
* High-speed bi-encoder fallback combines vector score, query term coverage, and exact phrase containment bonuses if cross-encoder weights are offline.

### 2.4 Hierarchical Graph RAG ([`graph_rag.py`](file:///d:/Python_Ai_Project/ChatBots_platform/services/chat-service/src/rag/graph_rag.py))
* Nodes represent entities (systems, concepts, protocols, components) and chunks.
* Edges represent semantic dependencies (`DEPENDS_ON`, `REGULATES`, `PROVIDES`, `CONTAINS`, `CONNECTS_TO`).
* Multi-hop traversal (`ego_graph`, radius=2) discovers cross-document relationships to answer complex enterprise questions that flat vector search cannot answer alone.

### 2.5 Corrective RAG (CRAG) ([`crag.py`](file:///d:/Python_Ai_Project/ChatBots_platform/services/chat-service/src/rag/crag.py))
* Evaluates chunk relevance against query intent before prompt construction.
* **Three-way branching:**
  1. **CORRECT ($\ge 0.75$):** Directly passes verified high-scoring chunks.
  2. **AMBIGUOUS ($0.40 - 0.74$):** Strips conversational filler, reformulates search terms, triggers secondary hybrid search, and merges deduplicated context.
  3. **INCORRECT ($< 0.40$):** Employs explicit anti-hallucination guardrail notice and fallback.

---

## 3. Verification & Benchmark Tests

All features are tested via `tests/test_agentic_mesh.py`:
- Entity and semantic triple mining: **PASSED**
- Hybrid RRF scoring & rank blending: **PASSED**
- Cross-encoder reranker inference: **PASSED**
- CRAG query reformulation and thresholding: **PASSED**
