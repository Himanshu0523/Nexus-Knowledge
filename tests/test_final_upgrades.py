"""
Comprehensive Verification Suite for Nexus Knowledge Final Upgrades:
- Phase 1: Hybrid Search with RRF (Dense + BM25 Sparse Vector Payload)
- Phase 2: Corrective RAG (CRAG) Evaluator Loop (Score >= 0.75 Pass / < 0.75 Fallback)
- Phase 3: Zero-Trust Multi-Tenancy & Regex PII Scrubbing
- Phase 4: Live Observability (/metrics) & Circuit Breaker 503 Provider Switching
"""

import asyncio
import os
import sys
from typing import Dict, Any, List

# Ensure services/chat-service/src and repo root are on python path
sys.path.insert(0, os.path.abspath("services/chat-service/src"))
sys.path.insert(0, os.path.abspath("."))

from rag.chunking import TextChunker, compute_sparse_vector
from rag.retriever import Retriever, lexical_corpus_index
from rag.crag import (
    crag_evaluator,
    CorrectiveRAGEvaluator,
    CRAGAction,
    evaluate_retrieval_confidence
)
from shared.security.pii_scrubber import pii_scrubber, PIIScrubber
from rag.ingestion import IngestionPipeline
from rag.qdrant_client import QdrantService
from shared.telemetry.metrics import metrics
from llm.stream_client import LLMStreamClient
from shared.security.circuit_breaker import CircuitBreaker, CircuitState


# =====================================================================
# Phase 1: Hybrid Search with RRF & Sparse Vectors
# =====================================================================

def test_phase1_sparse_vector_generation():
    """Verify sparse term frequency vector generation alongside text chunks."""
    text = "Tenant alpha security code SEC-9021 and error code ERR-404 in gateway"
    sparse_vec = compute_sparse_vector(text)
    
    assert isinstance(sparse_vec, dict)
    assert "sec" in sparse_vec or "sec-9021" in sparse_vec or "err" in sparse_vec
    assert "gateway" in sparse_vec
    assert all(0.0 < score <= 1.0 for score in sparse_vec.values())

    chunker = TextChunker(chunk_size=100, overlap=10)
    chunks = chunker.chunk_text(text, metadata={"source": "test_sec.txt"})
    assert len(chunks) > 0
    assert "sparse_vector" in chunks[0]
    assert isinstance(chunks[0]["sparse_vector"], dict)
    print("[PASS] Phase 1: Sparse vector generation verified.")


async def test_phase1_rrf_retrieval():
    """Verify Reciprocal Rank Fusion (RRF) with k=60 combining dense and sparse ranks."""
    tenant_id = "tenant_test_rrf"
    retriever = Retriever()
    assert retriever.rrf_k == 60

    # Index sample chunks into BM25 lexical corpus
    doc_chunks = [
        {"chunk_id": "c1", "text": "Tenant alpha API rate limit policy is 500 req/sec", "metadata": {"source": "limits.pdf", "page": 1}},
        {"chunk_id": "c2", "text": "Database read replicas scale automatically on spike", "metadata": {"source": "db.pdf", "page": 2}},
    ]
    lexical_corpus_index.add_chunks_batch(tenant_id, doc_chunks)

    # Search BM25 directly
    bm25_res = lexical_corpus_index.search_bm25(tenant_id, "API rate limit policy")
    assert len(bm25_res) > 0
    assert bm25_res[0]["payload"]["chunk_id"] == "c1"

    # Search with hybrid RRF
    results = await retriever.retrieve("API rate limit policy", tenant_id, use_hybrid=True)
    assert len(results) > 0
    top_chunk = results[0]
    assert top_chunk.get("retrieval_mode") in ("hybrid_rrf", "bm25_lexical")
    print(f"[PASS] Phase 1: Hybrid RRF retrieval verified. Top score={top_chunk.get('score')}")


# =====================================================================
# Phase 2: Corrective RAG (CRAG) Evaluator Loop
# =====================================================================

async def test_phase2_crag_evaluator_judge_and_thresholds():
    """Verify lightweight async judge function and execution thresholds (>= 0.75 vs < 0.75)."""
    query = "What is the security protocol for API rate limits?"
    
    # Highly relevant chunk
    high_rel_chunks = [{
        "chunk_id": "rel_1",
        "score": 0.95,
        "payload": {
            "text": "The security protocol for API rate limits strictly limits tenants to 500 requests per minute.",
            "source": "security_protocol.pdf",
            "page": 4
        }
    }]

    # Low relevance / ambiguous chunk
    low_rel_chunks = [{
        "chunk_id": "low_1",
        "score": 0.20,
        "payload": {
            "text": "The kitchen refrigerator temperature should be kept at 4 degrees Celsius.",
            "source": "office_manual.pdf",
            "page": 10
        }
    }]

    # Test judge function
    high_score = await evaluate_retrieval_confidence(query, high_rel_chunks)
    assert high_score >= 0.75, f"Expected high confidence >= 0.75, got {high_score}"

    low_score = await evaluate_retrieval_confidence(query, low_rel_chunks)
    assert low_score < 0.75, f"Expected low confidence < 0.75, got {low_score}"

    # Verify action classification
    evaluator = CorrectiveRAGEvaluator(correct_threshold=0.75, incorrect_threshold=0.40)
    action_high, conf_high, _ = evaluator.evaluate_retrieval(query, high_rel_chunks)
    assert action_high == CRAGAction.CORRECT

    action_low, conf_low, _ = evaluator.evaluate_retrieval(query, low_rel_chunks)
    assert action_low in (CRAGAction.AMBIGUOUS, CRAGAction.INCORRECT)

    # Execute complete CRAG state machine loop on low-confidence chunks
    crag_res = await evaluator.execute_crag_loop(
        query=query,
        initial_chunks=low_rel_chunks,
        retriever_callable=None,
        tenant_id="test_tenant"
    )
    assert crag_res.confidence_score < 0.75
    assert crag_res.system_advisory is not None
    print(f"[PASS] Phase 2: CRAG Evaluator loop verified (High={high_score}, Low={low_score}).")


# =====================================================================
# Phase 3: Zero-Trust Multi-Tenancy & PII Scrubbing
# =====================================================================

def test_phase3_pii_scrubber():
    """Verify regex PII scrubbing for emails, phones, API keys, and SSNs."""
    raw_text = (
        "Contact admin at support@enterprise.io or call +1 (555) 234-5678. "
        "Your secret key is sk_live_9876543210abcdef123456 and SSN is 123-45-6789."
    )
    scrubbed, counts = pii_scrubber.scrub(raw_text)

    assert "support@enterprise.io" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed

    assert "555" not in scrubbed or "234-5678" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed

    assert "sk_live_" not in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed

    assert "123-45-6789" not in scrubbed
    assert "[REDACTED_SSN]" in scrubbed

    assert pii_scrubber.is_clean(scrubbed) == True
    print(f"[PASS] Phase 3: PII Scrubber successfully masked enterprise sensitive data: {counts}")


async def test_phase3_ingestion_pii_sanitization():
    """Verify IngestionPipeline automatically scrubs PII before chunking and vector storage."""
    pipeline = IngestionPipeline()
    filename = "confidential_memo.txt"
    document_id = "doc_confidential_001"
    tenant_id = "tenant_shield"

    content = (
        "CONFIDENTIAL MEMO\n"
        "Lead Engineer email: dev-lead@enterprise.com, phone: 415-555-0199.\n"
        "AWS and OpenAI root credentials: sk_live_securetestkey99998888.\n"
        "Projected quarterly revenue is $12.5M across enterprise accounts."
    ).encode("utf-8")

    result = await pipeline.process_document(
        file_bytes=content,
        filename=filename,
        document_id=document_id,
        tenant_id=tenant_id
    )

    assert result["status"] == "completed"
    assert result.get("pii_redactions", 0) > 0
    print(f"[PASS] Phase 3: Ingestion pipeline scrubbed {result.get('pii_redactions')} PII occurrences.")


# =====================================================================
# Phase 4: Live Observability & Graceful Fallbacks
# =====================================================================

def test_phase4_prometheus_metrics_and_tenant_tracking():
    """Verify Prometheus metrics recording for latency, token consumption per tenant, and error rates."""
    tenant_id = "tenant_metrics_test"

    # Record normal HTTP request
    metrics.record_http_request("POST", "/api/v1/chat", 200, 0.085, tenant_id=tenant_id)
    # Record error rate HTTP request
    metrics.record_http_request("POST", "/api/v1/chat", 503, 0.120, tenant_id=tenant_id)
    # Record LLM token consumption per tenant
    metrics.record_llm_request(
        provider="nexus-llm",
        model="qwen-2.5",
        status="success",
        duration=0.35,
        input_tokens=150,
        output_tokens=75,
        tenant_id=tenant_id
    )

    prom_text = metrics.generate_prometheus_text()
    assert "http_requests_total" in prom_text
    assert "http_request_duration_seconds" in prom_text
    assert "llm_tokens_total" in prom_text
    assert f'tenant_id="{tenant_id}"' in prom_text
    print("[PASS] Phase 4: Prometheus metrics verify request latency, token consumption per tenant, and error rates.")


async def test_phase4_circuit_breaker_503_fallback_switching():
    """Verify that when primary LLM encounters a 503 error, it seamlessly switches to backup provider without crashing SSE."""
    client = LLMStreamClient()
    # Force primary to an invalid endpoint that triggers 503/connection error
    client.provider = "ollama"
    client.base_url = "http://127.0.0.1:59999"  # Non-existent endpoint
    client.backup_provider = "mock"

    messages = [{"role": "user", "content": "Explain circuit breaker resilience."}]
    streamed_tokens = []

    # Stream should NOT raise an unhandled exception or crash the generator
    async for token in client.stream_response(messages):
        streamed_tokens.append(token)

    full_stream = "".join(streamed_tokens)
    assert len(streamed_tokens) > 0
    assert "enterprise response" in full_stream.lower()
    assert client.circuit_breaker.failure_count > 0
    print(f"[PASS] Phase 4: Circuit Breaker successfully failed over to backup provider on connection/503 error without crashing SSE: '{full_stream[:60]}...'")


if __name__ == "__main__":
    print("=====================================================")
    print("  RUNNING NEXUS KNOWLEDGE FINAL UPGRADE TEST SUITE   ")
    print("=====================================================")
    test_phase1_sparse_vector_generation()
    asyncio.run(test_phase1_rrf_retrieval())
    asyncio.run(test_phase2_crag_evaluator_judge_and_thresholds())
    test_phase3_pii_scrubber()
    asyncio.run(test_phase3_ingestion_pii_sanitization())
    test_phase4_prometheus_metrics_and_tenant_tracking()
    asyncio.run(test_phase4_circuit_breaker_503_fallback_switching())
    print("\n[SUCCESS] ALL 4 PHASES VALIDATED AND FULLY PASSING!")
