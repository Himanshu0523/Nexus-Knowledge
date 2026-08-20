# Multi-Tenant AI Chatbot Platform

A production-grade, modular, language-agnostic AI chatbot platform supporting multi-turn conversation memory (PostgreSQL + Redis), vector document ingestion & retrieval-augmented generation (RAG with Qdrant), Server-Sent Events (SSE) token streaming, and official SDKs for Python, Node.js, Java, and C++.

---

## 🏗️ Platform Architecture

```text
                                Client Applications
                    (Python / Node.js / Java / C++ / Web / Mobile)
                                         │
                                         ▼
                                ┌─────────────────┐
                                │   API Gateway   │ (Port 8000)
                                └────────┬────────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                                │  Chat Service   │ (Port 8001)
                                └────────┬────────┘
                                         │
             ┌───────────────────────────┼───────────────────────────┐
             ▼                           ▼                           ▼
   ┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
   │ PostgreSQL (5432) │       │   Redis (6379)    │       │   Qdrant (6333)   │
   │  Persistent Chat  │       │ Ephemeral History │       │  Vector Database  │
   └───────────────────┘       └───────────────────┘       └───────────────────┘
```

---

## 🚀 Quick Start (Running the Project)

### Method 1: Using Docker Compose (Recommended)

Make sure **Docker Desktop** is running on your computer.

1. **Start all services in detached mode:**
   ```powershell
   docker-compose up -d --build
   ```

2. **Verify running container statuses:**
   ```powershell
   docker-compose ps
   ```

3. **View live logs across services:**
   ```powershell
   docker-compose logs -f
   ```

4. **Stop all services:**
   ```powershell
   docker-compose down
   ```

---

### Method 2: Running Services Locally (Without Docker Containers)

#### Prerequisites
- **Python 3.10+** installed.
- PostgreSQL running locally or remotely (configured via `DATABASE_URL`).
- Redis running locally or remotely (configured via `REDIS_HOST`).
- Qdrant running locally or remotely (configured via `QDRANT_HOST`).

#### Step 1: Start Chat Service (Port 8001)
Open a new terminal tab:
```powershell
cd services/chat-service
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
```

#### Step 2: Start API Gateway (Port 8000)
Open another terminal tab:
```powershell
cd api-gateway
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Testing & Verification

Once services are running, execute any of the included automated test scripts from the repository root directory:

### 1. Test Core Chat & Conversation Memory (Phase 3)
```powershell
python api-gateway/test_api.py
```
*Or using PowerShell:*
```powershell
.\api-gateway\test_api.ps1
```

### 2. Test Document Ingestion & RAG (Phase 4)
```powershell
python test_rag.py
```

### 3. Test Real-time SSE Token Streaming (Phase 6)
```powershell
python test_streaming.py
```
*Or using PowerShell:*
```powershell
.\test_streaming.ps1
```

### 4. Test Language SDK Contracts (Phase 7)
```powershell
python test_sdks.py
```

---

## 📖 Interactive API Documentation & Dashboards

When services are running, interactive Swagger UI documentation and admin dashboards are available at:

- **API Gateway Swagger Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Chat Service Swagger Documentation:** [http://localhost:8001/docs](http://localhost:8001/docs)
- **Qdrant Vector Database Web Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

## 📦 Language-Agnostic SDK Libraries

Client libraries are structured in the `sdks/` directory:

| Language | Location | Setup / Install |
| :--- | :--- | :--- |
| **Python** | `sdks/python/` | `pip install ./sdks/python` |
| **Node.js / TypeScript** | `sdks/node/` | `npm install ./sdks/node` |
| **Java** | `sdks/java/` | Build with `mvn clean install` |
| **C++** | `sdks/cpp/` | CMake header-only library (`include/chatbot/client.hpp`) |

---

## 🛠️ Environment Variables Configuration

Set these environment variables in `docker-compose.yml` or your local `.env`:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://chatbot:chatbot_password@postgres:5432/chatbot_db` | PostgreSQL connection string |
| `REDIS_HOST` | `redis` (or `localhost`) | Redis cache host |
| `REDIS_PORT` | `6379` | Redis cache port |
| `QDRANT_HOST` | `qdrant` (or `localhost`) | Qdrant vector database host |
| `QDRANT_PORT` | `6333` | Qdrant vector database port |
| `LLM_PROVIDER` | `mock` (or `ollama`, `openai`) | Provider engine for LLM inference |
| `EMBEDDING_MODEL` | `mock` (or `openai`, `huggingface`) | Embedding generator model |
