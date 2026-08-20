# Phase 9: Security & Multi-Tenant Protection Architecture

## Overview
Phase 9 enforces production-grade security, multi-tenant isolation, prompt injection defenses, and strict access controls across the Chatbot Platform.

---

## 🔒 1. Authentication & Authorization

- **API Keys:** Handled via HTTP `Authorization: Bearer <key>` or `X-API-Key` header.
- **Tenant Resolution:** Every valid API key resolves to a verified `tenant_id` at the API Gateway level before requests reach backend microservices.
- **Security Headers:** Automatic enforcement of `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, and `Strict-Transport-Security`.

---

## 🛡️ 2. Prompt Injection Defense (`PromptGuard`)

The `PromptGuard` engine inspects incoming user prompts and RAG contexts before feeding them to the LLM.

- **Inspection:** Scans against known injection primitives (e.g. `ignore previous instructions`, `reveal system prompt`, `exec sql`).
- **Sanitization:** Removes null bytes, unescaped control markers, and dangerous payload prefixes.
- **Enforcement Location:** Executed inside `ChatOrchestrator.process_message()` prior to context assembly.

---

## 🧼 3. Output Sanitization & Leak Prevention (`OutputGuard`)

The `OutputGuard` engine inspects generated LLM responses before delivering them to clients.

- **Redaction:** Automatically redacts leaked API keys (`sk_...`), Bearer tokens, or Sensitive PII (SSNs) from response payloads.
- **Output Inspection:** Protects against accidental secret disclosures in multi-tenant environments.

---

## 🏢 4. Multi-Tenant Data Isolation

1. **Database Scoping (PostgreSQL):** All conversation, message, and document queries strictly filter on `WHERE tenant_id = :tenant_id`.
2. **Cache Isolation (Redis):** Keys are namespaced by tenant (e.g. `tenant:<tenant_id>:conv:<conv_id>`).
3. **Vector Search Isolation (Qdrant):** Every similarity search includes explicit Qdrant payload filters matching `tenant_id`.

---

## ⚙️ 5. Role-Based Tool Execution (`ToolPermissionManager`)

| Role | Allowed Tools |
| :--- | :--- |
| **admin** | `calculator`, `weather`, `web_search`, `document_reader`, `system_info` |
| **developer** | `calculator`, `weather`, `web_search`, `document_reader` |
| **member** | `calculator`, `weather` |
| **viewer** | `calculator` |

- **High-Risk Guard:** High-risk actions (`delete_database`, `send_email`) require explicit human confirmation.

---

## ⚡ 6. Request Tracing & Correlation

- **`X-Request-ID` Header:** Automatically generated and propagated across Gateway, Chat Orchestrator, LLM calls, and Kafka Event logs.
