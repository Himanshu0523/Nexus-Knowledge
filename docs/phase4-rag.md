# Phase 4: RAG (Retrieval-Augmented Generation) Specification

## Architecture Overview

```text
              Documents (PDF, DOCX, TXT)
                         │
                         ▼
                  Document Parser
                         │
                         ▼
                   Text Chunker
                         │
                         ▼
                  Embedding Engine
                         │
                         ▼
               Qdrant Vector Database
                         │
                         ▼
             Retriever + Re-ranker
                         │
                         ▼
              Chat Orchestrator + LLM
```

## Features Implemented
1. **Multi-Format Parsers**: PDF (`pypdf`), DOCX (`python-docx`), TXT/MD.
2. **Text Chunking**: Sliding-window chunking (500 tokens, 50 token overlap) with cleaning rules.
3. **Embeddings Engine**: Supports mock, OpenAI, HuggingFace, and SentenceTransformer embeddings.
4. **Vector Storage**: Qdrant vector database integration with tenant isolation filters.
5. **Retrieval & Reranking**: Vector similarity retrieval + hybrid lexical/score re-ranker.
6. **Chat Orchestration**: Combines conversation memory (Postgres/Redis) with RAG context citations.
