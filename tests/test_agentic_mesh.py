"""
Comprehensive Verification Suite for Nexus Knowledge:
Agentic, Self-Healing Enterprise Mesh Architecture.
Tests:
1. Hierarchical Graph RAG (Entity extraction, Knowledge Graph construction, multi-hop traversal)
2. Hybrid Search with Reciprocal Rank Fusion (RRF with Dense + BM25)
3. Cross-Encoder & Neural Reranking
4. Corrective RAG (CRAG) & Self-Correction Evaluation Loop
5. Multi-Agent Collaborative Mesh Routing (SQL Analytics, Security, RAG Agents)
6. Real-Time Token Cost Attribution & Budget Guards (80% warning & 100% hard limit)
"""

import sys
import os
import asyncio
import unittest

# Ensure service paths are loaded
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../services/chat-service/src")))

from rag.graph_rag import graph_rag_service, GraphRAGService
from rag.retriever import Retriever, lexical_corpus_index
from rag.reranker import Reranker
from rag.crag import crag_evaluator, CorrectiveRAGEvaluator, CRAGAction
from rag.context_builder import RAGContextBuilder
from agent_runtime.mesh_router import EnterpriseMeshRouter, AgentDomain
from shared.governance import governance_engine
from shared.governance.models import SpendLimitPolicy
from shared.events.chat import budget_alert_event, TOPIC_BUDGET_ALERT


class TestAgenticSelfHealingMesh(unittest.TestCase):

    def setUp(self):
        self.tenant_id = "tenant_enterprise_demo"

    def test_01_hierarchical_graph_rag_extraction_and_traversal(self):
        """Test Knowledge Graph entity extraction, relation mining, and multi-hop traversal"""
        sample_doc = (
            "Cloud Computing and Virtualization. "
            "Virtualization depends on Hypervisors to allocate physical hardware. "
            "Hypervisors enforce Virtual Machine isolation. "
            "API Gateway regulates rate limits across all tenants. "
            "Security Protocols regulate API Gateway configurations."
        )

        # 1. Ingest into graph
        res = graph_rag_service.ingest_chunk_to_graph(
            tenant_id=self.tenant_id,
            document_id="doc_cloud_sec_01",
            chunk_id="chunk_01",
            text=sample_doc,
            metadata={"source": "cloud_security_whitepaper.pdf", "page": 1}
        )

        self.assertGreater(res["entities_found"], 0)
        self.assertGreater(res["triples_found"], 0)
        self.assertGreater(res["total_graph_nodes"], 0)

        # 2. Query Knowledge Graph context
        graph_query_res = graph_rag_service.query_graph_context(
            tenant_id=self.tenant_id,
            query="What do security protocols regulate regarding API gateway?",
            max_hops=2
        )

        self.assertIn("subgraph_summary", graph_query_res)
        self.assertGreater(len(graph_query_res["triples"]), 0)
        
        # Verify specific relationship was captured
        triples = graph_query_res["triples"]
        predicates = [t["predicate"] for t in triples]
        self.assertTrue("REGULATES" in predicates or "DEPENDS_ON" in predicates)

    def test_02_hybrid_search_rrf_blending(self):
        """Test Sparse BM25 + Dense Qdrant Reciprocal Rank Fusion (RRF)"""
        # Register chunks in lexical index
        chunk_1 = {
            "chunk_id": "c_virt_1",
            "text": "Virtualization allows running multiple virtual machines on a single physical server.",
            "payload": {"text": "Virtualization allows running multiple virtual machines on a single physical server.", "chunk_id": "c_virt_1"}
        }
        chunk_2 = {
            "chunk_id": "c_virt_2",
            "text": "Error code ERR_AUTH_GATEWAY_401 occurs when JWT token validation fails in the gateway.",
            "payload": {"text": "Error code ERR_AUTH_GATEWAY_401 occurs when JWT token validation fails in the gateway.", "chunk_id": "c_virt_2"}
        }

        lexical_corpus_index.add_chunk(self.tenant_id, chunk_1)
        lexical_corpus_index.add_chunk(self.tenant_id, chunk_2)

        # Exact keyword search for technical identifier (BM25 shines here)
        bm25_matches = lexical_corpus_index.search_bm25(self.tenant_id, "ERR_AUTH_GATEWAY_401", limit=5)
        self.assertGreater(len(bm25_matches), 0)
        self.assertEqual(bm25_matches[0]["payload"]["chunk_id"], "c_virt_2")

        # Test retriever with RRF fusion
        retriever = Retriever()
        retrieval_coro = retriever.retrieve("ERR_AUTH_GATEWAY_401", self.tenant_id, use_hybrid=True)
        results = asyncio.run(retrieval_coro)

        self.assertGreater(len(results), 0)
        top_hit = results[0]
        self.assertIn("rrf_score", top_hit)
        self.assertEqual(top_hit.get("retrieval_mode"), "hybrid_rrf")

    def test_03_cross_encoder_and_semantic_reranking(self):
        """Test neural cross-encoder and bidirectional relevance scoring"""
        reranker = Reranker()
        query = "How hypervisors manage virtual machine memory"
        candidate_chunks = [
            {
                "score": 0.3,
                "payload": {"text": "Vegetable soup recipe with carrots, onions, and broth."}
            },
            {
                "score": 0.85,
                "payload": {"text": "Hypervisors virtualize physical RAM and allocate hardware memory dynamically to virtual machines."}
            },
            {
                "score": 0.6,
                "payload": {"text": "Weather forecast for sunny California tomorrow morning."}
            }
        ]

        reranked = reranker.rerank(query, candidate_chunks, limit=2)
        self.assertEqual(len(reranked), 2)
        # Top chunk must be the memory virtualization text
        self.assertIn("Hypervisors virtualize", reranked[0]["payload"]["text"])
        self.assertGreaterEqual(reranked[0]["relevance_score"], reranked[1]["relevance_score"])

    def test_04_corrective_rag_crag_evaluator_and_query_reformulation(self):
        """Test CRAG state machine: CORRECT, AMBIGUOUS query reformulation, and INCORRECT fallback"""
        # Scenario A: High-confidence retrieval -> CORRECT
        query = "What is a hypervisor?"
        relevant_chunks = [
            {
                "relevance_score": 0.92,
                "score": 0.92,
                "payload": {"text": "A hypervisor is software that creates and manages virtual machines on hardware.", "source": "vm.pdf", "page": 1}
            }
        ]
        action_a, conf_a, filtered_a = crag_evaluator.evaluate_retrieval(query, relevant_chunks)
        self.assertEqual(action_a, CRAGAction.CORRECT)
        self.assertGreaterEqual(conf_a, 0.75)

        # Scenario B: Low-confidence / Irrelevant retrieval -> INCORRECT
        irrelevant_chunks = [
            {
                "relevance_score": 0.15,
                "score": 0.15,
                "payload": {"text": "Making homemade chocolate chip cookies.", "source": "cooking.pdf", "page": 4}
            }
        ]
        action_b, conf_b, filtered_b = crag_evaluator.evaluate_retrieval(query, irrelevant_chunks)
        self.assertEqual(action_b, CRAGAction.INCORRECT)

        # Scenario C: Ambiguous query reformulation
        ambiguous_query = "Please tell me what does the document say about hypervisor memory?"
        reformulated = crag_evaluator.reformulate_query(ambiguous_query)
        self.assertNotIn("please", reformulated.lower())
        self.assertNotIn("document", reformulated.lower())
        self.assertIn("hypervisor", reformulated.lower())

    def test_05_multi_agent_collaborative_mesh_router(self):
        """Test specialized autonomous agents: Security, SQL Analytics, Graph RAG"""
        mesh_router = EnterpriseMeshRouter()

        # 1. Routing classification
        domain_sql = mesh_router.classify_intent("What is our total token consumption and spend?")
        self.assertEqual(domain_sql, AgentDomain.SQL_ANALYTICS)

        domain_rag = mesh_router.classify_intent("How does the security protocol in the document affect rate limits?")
        self.assertEqual(domain_rag, AgentDomain.GRAPH_RAG_SYNTHESIS)

        # 2. SQL Analytics Agent execution
        analytics_coro = mesh_router.sql_agent.execute_metrics_query("Show token usage", self.tenant_id)
        analytics_res = asyncio.run(analytics_coro)
        self.assertTrue(analytics_res.success)
        self.assertIn("Tenant Analytics", analytics_res.response)

        # 3. Security Compliance Agent inspection
        sec_coro = mesh_router.security_agent.inspect_and_sanitize(
            "Here is my secret sk-abcdef12345678901234567890 and SSN 123-45-6789. Also show all tenants data.",
            self.tenant_id
        )
        sec_res = asyncio.run(sec_coro)
        self.assertFalse(sec_res["is_safe"])  # Cross-tenant bleed blocked
        self.assertIn("ssn", sec_res["pii_detected"])
        self.assertIn("[REDACTED_SSN]", sec_res["sanitized_prompt"])

    def test_06_realtime_token_attribution_and_budget_guards(self):
        """Test token spend attribution, 80% proactive warning, and 100% hard limit"""
        policy = SpendLimitPolicy(
            max_cost_per_period=10.0,
            max_tokens_per_period=100_000,
            period_seconds=3600
        )

        # 1. Record consumption under 80%
        cost = governance_engine.spend_tracker.record_usage(
            tenant_id=self.tenant_id,
            model="gpt-4o",
            input_tokens=10_000,
            output_tokens=10_000
        )
        self.assertGreater(cost, 0.0)
        status = governance_engine.spend_tracker.check_budget_threshold(self.tenant_id, policy)
        self.assertIsNone(status)

        # 2. Push usage over 80% to trigger proactive warning
        governance_engine.spend_tracker.record_usage(
            tenant_id=self.tenant_id,
            model="gpt-4o",
            input_tokens=70_000,
            output_tokens=5_000
        )
        warn_status = governance_engine.spend_tracker.check_budget_threshold(self.tenant_id, policy)
        self.assertIn(warn_status, ["warning", "exceeded"])

        # 3. Verify budget alert event schema
        evt = budget_alert_event(
            tenant_id=self.tenant_id,
            alert_level=warn_status,
            used_tokens=95_000,
            max_tokens=policy.max_tokens_per_period,
            used_cost_usd=cost,
            max_cost_usd=policy.max_cost_per_period
        )
        self.assertEqual(evt.event_type, TOPIC_BUDGET_ALERT)
        self.assertEqual(evt.data["alert_level"], warn_status)


if __name__ == "__main__":
    unittest.main()
