# Nexus AI — Future Roadmap Implementation Plan (Stages 11–20)

This document picks up where the current platform leaves off. Stages 1–10 (API contract, basic chat, memory, RAG, tools, streaming, SDKs, Kafka, security, K8s deployment) are functionally complete. This plan covers what turns that into a genuinely production-grade, fully open-source AI platform — **what to build and why**, not how to code it.

**Governing principle for everything below:**
```
Need → Measure → Implement → Test → Keep
```
Not "new technology exists → add it." Every stage should be justified by an actual limitation you've hit, not a feature you read about.

---

## Where the platform is headed

```
                 NEXUS AI
                    │
        ┌───────────┴───────────┐
        │                       │
   PLATFORM CORE            AI CORE
        │                       │
   API Gateway              AI Orchestrator
   Auth / RBAC              RAG
   Tenancy                  Agents
   Rate Limit               Tools
   SDKs                     Memory
        │                       │
        └───────────┬───────────┘
                    ▼
              EVENT PLATFORM (Kafka)
                    │
       ┌────────────┼────────────┐
     Audit       Analytics    Moderation
                    │
              OBSERVABILITY
       OpenTelemetry + Prometheus + Grafana
                    │
              PRODUCTION INFRA
             Docker + Kubernetes
```

## Stage priority overview

| Stage | Focus | Priority | Depends on |
|---|---|---|---|
| 11 | Production hardening | Critical | Nothing — do this first |
| 12 | Observability | Critical | Stage 11 |
| 13 | Advanced RAG | Critical | Stage 12 (so you can measure the impact) |
| 14 | Agent runtime | Critical | Stage 11 (needs sandboxing infra) |
| 15 | Model gateway / LLM routing | High | Stage 12 |
| 16 | Evaluation system | Critical | Stages 13 & 14 (needs something to evaluate) |
| 17 | AI governance | High | Stage 15 |
| 18 | High availability | Medium | All of the above stable |
| 19 | Developer platform | High | Stage 17 (needs policy layer for external users) |
| 20 | Enterprise platform | High | Stage 18 & 19 |

---

## Stage 11 — Production Hardening

**Why this is first:** every stage after this one adds more moving parts. If the current system isn't resilient to a single dependency failing, adding RAG improvements or agents just gives you more ways to fail, not more capability. This is the least exciting stage and the most important one.

**What "hardening" actually means here:**
- **Timeouts** on every outbound call (LLM, Qdrant, Postgres, Kafka) — an unbounded call to a slow dependency is the single most common cause of cascading outages in service-oriented systems.
- **Retries with backoff** for transient failures, but only on idempotent operations.
- **Circuit breakers** so a struggling downstream service (e.g. the LLM provider) doesn't get hammered with retries that make its situation worse — the gateway should "trip" and fail fast for a cooldown period instead.
- **Graceful shutdown** — in-flight requests should finish before a pod terminates during a deploy or scale-down event.
- **Health and readiness checks** — distinct concepts: health = "is this process alive," readiness = "is this process able to serve traffic right now" (e.g. not yet connected to Redis/Valkey). Kubernetes uses both differently.
- **Connection pooling** for Postgres and Qdrant so you're not opening a new connection per request.
- **Kafka retry + dead-letter queues** — a message that repeatedly fails processing (e.g. malformed event) needs somewhere to go other than blocking the whole topic.
- **Request IDs** propagated across every service call, so a single user-facing error can be traced through gateway → chat service → LLM → Kafka consumer.

**Idempotency — the most important single addition here.**
The problem: a client sends `POST /chat`, the server processes it successfully, but the response is lost in transit (network blip, timeout). The client — correctly — retries. Without idempotency protection, you now have two LLM calls, two Kafka events, and possibly two billed generations for one user action.

The fix is an `Idempotency-Key` header the client generates per logical request. The server checks an idempotency store (can be Valkey) before processing: if the key was already handled, return the stored result instead of reprocessing. This one mechanism prevents duplicate charges, duplicate audit events, and duplicate side effects across the entire platform — it's disproportionately valuable for the effort involved.

**Exit criteria for this stage:** you can kill any single dependency (Qdrant, Kafka, the LLM backend) in a test environment and the platform degrades predictably — returns clear errors or fallback behavior — rather than hanging, crashing, or silently corrupting data.

---

## Stage 12 — Observability

**Why now:** you cannot responsibly build Stage 13 (RAG improvements) or Stage 16 (evaluation) without visibility into what the system is currently doing. "We added reranking and it feels faster" is not an engineering claim — it needs numbers.

**The distinction that matters:** logging is not observability. Logs tell you what happened in one place; observability lets you ask arbitrary questions about system behavior across services after the fact, without having predicted the question in advance.

**Three pillars:**
- **Metrics** (Prometheus) — numeric time series: request rate, error rate, latency percentiles.
- **Traces** (OpenTelemetry) — the path a single request takes across every service it touches, with timing at each hop. This is what lets you answer "why was this one request slow" instead of just "the average is slow."
- **Logs** (Loki, or similar) — structured, correlated to trace IDs so you can jump from a slow trace directly to the relevant log lines.

**What specifically to monitor, and why each matters:**
- **API latency (P50/P95/P99)** — averages hide the experience of your worst-served users; P95/P99 don't.
- **LLM latency and token throughput** — usually your biggest latency contributor and the one most affecting perceived responsiveness.
- **RAG latency** (embedding + Qdrant search + reranking, measured separately) — tells you exactly which stage of retrieval to optimize.
- **Postgres / Valkey / Qdrant latency** — isolates whether a slowdown is your infra or the LLM itself.
- **Kafka consumer lag** — a growing lag means your audit/analytics/moderation consumers are falling behind real-time, which matters a lot for moderation specifically.
- **Tool call latency and failure rate** — agents that call external tools are only as reliable as those tools.
- **SSE connection count** — streaming connections are stateful and consume server resources differently than normal requests; you need to know how many are open.
- **Error rate by service** — isolates *where* failures originate, not just that they're happening.
- **Per-tenant usage** — the foundation for both cost governance (Stage 17) and abuse detection.

**Exit criteria:** given any user complaint ("my request was slow" or "I got an error"), you can find the specific trace and identify exactly which service/dependency caused it, without guessing.

---

## Stage 13 — Advanced RAG

**Why this matters more than adding new features:** your RAG quality directly determines whether users trust the platform's answers. A fast, well-observed platform serving mediocre RAG results is still a mediocre product.

**Current pipeline (simple, works, has ceilings):**
```
Document → Chunk → Embed → Qdrant → Top K → LLM
```

**What each future addition solves:**

- **Query rewriting** — user questions are often underspecified or reference prior conversation ("what about the second one?"). Rewriting the query using conversation context before embedding it substantially improves retrieval accuracy for multi-turn conversations.
- **Hybrid retrieval (vector + keyword)** — pure vector search is bad at exact-match queries: error codes, product SKUs, proper nouns that weren't well-represented in embedding training data. Combining vector similarity with traditional keyword search (BM25) and merging results covers both cases.
- **Reranking** — retrieve a wider net (e.g. top 20) with cheap vector search, then use a more expensive but more accurate cross-encoder model to rerank down to the best 3–5 before they hit the LLM's context window. This is usually the single highest-leverage RAG improvement you can make.
- **Metadata filtering** — letting retrieval be scoped by document type, date, tenant, or access level, not just semantic similarity. Critical for multi-tenant isolation of the knowledge base itself, not just the database rows.
- **Parent-child chunking** — search against small, precise chunks (good for matching), but return the larger parent section to the LLM (good for context). Solves the tension between chunk size for search accuracy vs. chunk size for answer quality.
- **Document versioning** — when a source document is updated, stale chunks from the old version need to be identified and retired, not just added to alongside the new ones.
- **Citation generation** — the answer should be traceable back to the specific chunks that produced it. This is often a hard *enterprise* requirement (users need to verify claims), not just a nice-to-have.
- **Retrieval evaluation** — you need a way to measure whether a given change (new chunking strategy, new reranker) actually improved retrieval, which is what Stage 16 formalizes.

**Exit criteria:** you can point to specific before/after metrics (recall, faithfulness, citation accuracy) showing that a RAG change improved results — not just a subjective impression.

---

## Stage 14 — Agent Runtime

**Why this needs its own stage rather than being "more tools":** the current model (LLM → tool → result → LLM) has no safety boundary. As soon as an LLM can decide to call arbitrary tools without a permission layer, you've built a system where a prompt injection attack or a model mistake can take real actions — hitting a database, sending an email, spending money on an API call.

**Core architectural shift:** move from "LLM directly calls tools" to a planner/orchestrator pattern where the LLM proposes actions and a separate, non-LLM-controlled layer decides whether to allow them.

**The permission chain that should sit between "LLM wants to call a tool" and "tool actually executes":**
1. **Tool Registry** — the authoritative list of what tools exist and their schemas.
2. **Permission Manager** — is *this* tenant, *this* user, *this* conversation allowed to use *this* tool at all?
3. **Schema validation** — does the LLM's proposed call match the tool's expected input shape? (Prevents malformed or injected parameters.)
4. **Policy check** — business-level rules beyond raw permission (e.g. "database query tool can only run SELECT, never DELETE").
5. **Execution sandbox** — the tool actually runs in an isolated context with its own resource limits, so a runaway or malicious tool call can't affect the rest of the system.

**Why the planner/validator loop matters:** rather than a single LLM call deciding everything, a controlled loop (plan → act → validate result → decide "done" or "continue") gives you a place to insert safety checks between every step, and a natural point to log and audit every decision the agent made — which matters enormously for debugging when an agent does something unexpected.

**Exit criteria:** you can demonstrate that a malicious or malformed tool-call attempt (e.g. an injected instruction trying to call the database tool with a destructive query) is rejected by the permission/policy layer before it ever reaches the sandbox, and that the rejection is logged.

---

## Stage 15 — Open-Source LLM Gateway

**The problem being solved:** right now the chat service presumably talks to one specific LLM backend directly. That means every part of the code that generates a response has an implicit dependency on exactly one model, one deployment, one provider. Any change — swapping models, adding a fallback, giving different tenants different models — requires touching the chat service itself.

**The fix:** insert a gateway layer between the chat service and the actual model backends (vLLM, Ollama, or others). The chat service should only know "generate a response for this conversation" — it should have no knowledge of which model served that request, which GPU it ran on, or what the fallback chain looks like.

**What the gateway is responsible for that the chat service shouldn't be:**
- Which model handles this request (could vary by tenant, by task complexity, by cost tier)
- Which underlying deployment serves that model (vLLM for high-throughput self-hosted serving, Ollama for lightweight/local)
- Fallback behavior if the primary model/deployment is unavailable
- Per-tenant context length limits and policy
- GPU/resource allocation, if running self-hosted models

**Why vLLM specifically for the self-hosted path:** it's built for higher-throughput serving than something like Ollama, which is oriented more toward simplicity and local/single-user use. Having both available behind the gateway lets you use Ollama for lightweight or development scenarios and vLLM for production throughput, without the rest of the platform caring which one is actually running.

**Exit criteria:** you can add, remove, or swap a model backend without changing a single line in the chat service — only gateway-level configuration changes.

---

## Stage 16 — AI Evaluation System

**Why this is the stage that changes what kind of project this is:** everything up to this point makes the platform more reliable and more capable. This stage is what lets you know, with evidence, whether changes you make are actually improvements — which is the difference between an AI *application* and an AI *engineering platform*.

**The core question this stage answers:** "Is the AI actually getting better?" Without a formal evaluation system, this question gets answered by vibes — someone tries a few prompts, decides it feels better, and ships it. That doesn't scale, and it doesn't catch regressions.

**Structure:**
```
Test Dataset → Evaluation Runner → {RAG test, LLM test, Agent test} → Evaluator → Metrics
```

**What to measure, and why each one is non-obvious but important:**
- **Answer correctness** — the baseline metric, but insufficient alone.
- **Faithfulness** — does the answer actually reflect what the retrieved context said, or did the model add unsupported claims? This catches hallucination even when the final answer happens to sound right.
- **Context relevance** — were the retrieved chunks actually relevant to the question, independent of whether the final answer was good? Separates retrieval quality from generation quality.
- **Retrieval recall** — of all the chunks that *should* have been retrieved for a given question, how many actually were?
- **Citation correctness** — if the system claims a fact came from a specific source, did it actually?
- **Tool accuracy** — for agent tasks, did the agent choose the right tool and use it correctly?
- **Latency and token cost** — quality improvements that double cost or latency need to be weighed against that tradeoff explicitly, not discovered after rollout.
- **Safety and prompt injection resistance** — does the system resist adversarial inputs designed to make it ignore instructions or leak data?

**What this unlocks:** formal A/B comparison — Model A vs. Model B, RAG pipeline v1 vs. v2 — backed by consistent metrics on a held-out test set, rather than subjective judgment calls before every change.

**Exit criteria:** any proposed change to the model, RAG pipeline, or agent logic can be run against the evaluation suite before rollout, producing a quantified before/after comparison.

---

## Stage 17 — AI Gateway / Governance

**Why this is distinct from the LLM Gateway in Stage 15:** Stage 15 solves *routing* (which model serves a request). This stage solves *policy* (what is this tenant/user allowed to do at all). They're related but answer different questions.

**What this layer controls:**
- Which tenant can access which model (cost tiers, capability tiers)
- Maximum tokens per request and per period
- Maximum cost per tenant per period
- Which tools a given tenant/plan is allowed to use
- Which knowledge bases a tenant can query against
- Data retention policy per tenant (some enterprise customers will have contractual retention requirements)
- PII handling policy — what gets scrubbed, logged, or blocked before it reaches the model

**Why this matters commercially, not just technically:** this is the layer that makes it possible to actually sell different tiers of the platform — a smaller tenant on a lightweight model with basic tools, a larger tenant with a bigger model, full RAG, and database access — enforced consistently rather than through ad hoc checks scattered across services.

**Exit criteria:** tenant-specific policy (model access, tool access, spend limits) is enforced at a single governance layer, not duplicated or inconsistently checked across multiple services.

---

## Stage 18 — High Availability

**Why this is explicitly *not* an early-stage concern:** HA (replicas, multi-node clusters, load-balanced pools for every service) is the highest-complexity, highest-cost stage on this list, and it only pays off once you have real traffic and real uptime commitments to meet. Building it before Stages 11–17 are stable means you're operating a complex distributed system on top of a foundation you haven't yet proven reliable.

**What HA means for each component once you get here:**
- **PostgreSQL** — primary/replica setup with failover.
- **Valkey** — primary/replica for cache and idempotency-store durability.
- **Qdrant** — multi-node cluster so vector search survives a node failure.
- **Kafka** — multi-broker cluster (Kafka is designed for this from the start, but it needs to actually be configured and tested, not just assumed).
- **Compute** — multiple Kubernetes nodes/replicas behind a load balancer for every stateless service.

**Exit criteria:** you can take down any single node/replica of any component in a staging environment and the platform continues serving traffic without manual intervention.

---

## Stage 19 — Developer Platform

**Why this is where "language-agnostic" becomes a real product rather than an architectural nicety:** SDKs sitting in a monorepo subfolder are a promise, not a product. This stage is about turning the platform into something external developers can actually build on.

**What's needed beyond the SDKs themselves:**
- **API key management** — self-serve creation, rotation, and revocation, not a hardcoded key in a README.
- **Developer dashboard** — where a developer sees their usage, keys, and projects.
- **Usage dashboard** — token consumption, request volume, cost — visible to the developer, not just internal ops.
- **OpenAPI specification** — machine-readable API definition that keeps SDKs and docs from drifting out of sync with the actual API.
- **SDK documentation** — separate from API documentation; developers need language-specific guidance, not just endpoint references.
- **Webhook support** — lets external systems react to platform events (new message, tool call completed) without polling.
- **Versioned APIs** — a v1 contract that doesn't silently change out from under existing integrations when v2 ships.

**Why this depends on Stage 17 (governance):** you cannot safely expose the platform to external developers without the policy layer that limits what any given API key can do and spend.

**Exit criteria:** an external developer with no access to your codebase can sign up, get an API key, read the docs, and integrate the platform into their own application without contacting you.

---

## Stage 20 — Enterprise Platform

**This is the mature-state architecture the earlier stages are building toward, organized by concern:**

```
Nexus AI
├── Identity          — JWT, OAuth, SSO
├── Tenancy           — Organizations, Projects, Users
├── AI                — Models, RAG, Agents, Tools
├── Platform           — API, SDKs, Webhooks, Events
├── Governance         — Audit, RBAC, Policies, Data retention
└── Observability       — Metrics, Logs, Traces, Evaluation
```

Nothing in this stage is a genuinely new capability — it's the point where every earlier stage's output (identity from your security work, governance from Stage 17, observability from Stage 12, evaluation from Stage 16) is organized into a coherent product surface that an enterprise buyer's technical evaluation team can assess against their own checklist (SSO support, audit log completeness, data residency, RBAC granularity).

**Exit criteria:** you can walk through an enterprise security/compliance questionnaire (the kind larger customers require before purchase) and answer every question with an existing platform capability, not a promise of future work.

---

## Recommended fully open-source stack

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI | MIT licensed, mature async support |
| Gateway / reverse proxy | Nginx or Envoy | Both open source, Envoy has stronger observability integration |
| Cache / session store | **Valkey** (not Redis) | BSD-licensed, Linux Foundation-backed community fork; avoids Redis's newer source-available licensing |
| Relational database | PostgreSQL | Permissive license, industry standard |
| Vector database | Qdrant | Apache 2.0 |
| Event streaming | Apache Kafka | Apache 2.0 |
| LLM serving (throughput) | vLLM | Apache 2.0, built for high-throughput self-hosted serving |
| LLM serving (lightweight/local) | Ollama | Good for dev and low-volume scenarios |
| Embeddings | sentence-transformers | Apache 2.0 |
| Reranking | sentence-transformers cross-encoder models | Same licensing family as embeddings |
| Containers | Docker | Industry standard |
| Orchestration | Kubernetes | Apache 2.0 |
| Metrics | Prometheus | Apache 2.0 |
| Dashboards | Grafana | AGPLv3 — open source but copyleft; confirm this fits your distribution model |
| Tracing | OpenTelemetry | Apache 2.0 |
| Log aggregation | Loki | AGPLv3, same consideration as Grafana |
| Secrets management | HashiCorp Vault | Check current license terms before adopting — HashiCorp's licensing has changed in recent years, similar to the Redis situation |
| CI/CD | GitHub Actions or GitLab CI | Free tier available; not self-hosted infrastructure per se |

**The one correction that matters most if "fully open source" is a hard requirement:** replace Redis with Valkey. Redis's licensing changed to a source-available model in recent versions; Valkey is the community-maintained fork that preserves full open-source licensing with API compatibility, so the swap doesn't require rewriting your caching or memory-store logic.

---

## What to deliberately not build yet

Adding these before you need them adds operational complexity without corresponding benefit at this stage:

- Service mesh
- Multi-region deployment
- GPU cluster orchestration
- Splitting into many more microservices than you currently have
- Kubernetes operators for every component
- A heavyweight agent framework beyond what Stage 14 requires
- Graph database
- Elasticsearch (Qdrant's payload filtering covers most metadata-search needs without a second search system)
- Multiple vector databases
- Multiple message brokers
- Multiple API gateways

Each of these is a legitimate tool in the right context — but adopting them before your actual traffic, team size, or compliance requirements demand it just adds surface area to maintain and debug.

---

## Sequencing summary

```
NOW
 │
 ▼
1. Production Hardening        (Stage 11)
 │
 ▼
2. Observability                (Stage 12)
 │
 ▼
3. Advanced RAG                 (Stage 13)
 │
 ▼
4. Agent Runtime + Sandbox      (Stage 14)
 │
 ▼
5. LLM Gateway (vLLM routing)   (Stage 15)
 │
 ▼
6. AI Evaluation System         (Stage 16)
 │
 ▼
Developer Platform              (Stage 19)
 │
 ▼
Enterprise Governance           (Stage 17, 20)
 │
 ▼
High Availability               (Stage 18)
```

The current stage is not "add more architecture" — it's **Production Hardening → Observability → Advanced RAG → Agent Runtime → LLM Gateway → Evaluation**, in that order, each one built on evidence from the stage before it rather than added speculatively.
