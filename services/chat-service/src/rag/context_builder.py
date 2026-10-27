"""
Enhanced RAG Context Builder for Nexus Knowledge.
Combines:
1. Hybrid RRF Retrieval (Dense + BM25)
2. Cross-Encoder Re-Ranking
3. Hierarchical Graph RAG Knowledge Graph Traversal
4. Corrective RAG (CRAG) Self-Correction Evaluation Loop
"""

from typing import List, Dict, Any, Optional
import logging
from .retriever import Retriever
from .reranker import Reranker
from .graph_rag import graph_rag_service
from .crag import crag_evaluator, CRAGResult, CRAGAction

logger = logging.getLogger(__name__)


class RAGContextBuilder:
    """
    Builds rich, self-healing, graph-augmented context for the LLM.
    """
    
    def __init__(self):
        self.retriever = Retriever()
        self.reranker = Reranker()
        self.max_context_length = 4000
    
    async def build_context(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: Optional[str] = None,
        use_graph_rag: bool = True,
        use_crag: bool = True
    ) -> Dict[str, Any]:
        """
        Build unified RAG context integrating Hybrid RRF, Cross-Encoder, Graph RAG, and CRAG.
        """
        filters = {}
        if knowledge_base_id:
            filters["knowledge_base_id"] = knowledge_base_id

        # 1. Hybrid Search (Dense Vector + BM25 Lexical with Reciprocal Rank Fusion)
        raw_chunks = await self.retriever.retrieve(query, tenant_id, filters, use_hybrid=True)

        # 2. Cross-Encoder Re-ranking
        reranked_chunks = self.reranker.rerank(query, raw_chunks)

        # 3. Corrective RAG (CRAG) Evaluation Loop
        crag_result: Optional[CRAGResult] = None
        if use_crag:
            crag_result = await crag_evaluator.execute_crag_loop(
                query=query,
                initial_chunks=reranked_chunks,
                retriever_callable=self.retriever.retrieve,
                tenant_id=tenant_id,
                filters=filters
            )
            final_chunks = crag_result.chunks
            sources = crag_result.sources
        else:
            final_chunks = reranked_chunks
            sources = [
                {
                    "document": c.get("payload", {}).get("source", "Unknown"),
                    "page": c.get("payload", {}).get("page", "N/A"),
                    "relevance_score": c.get("relevance_score", c.get("score", 0.0)),
                    "chunk_id": c.get("payload", {}).get("chunk_id")
                }
                for c in final_chunks
            ]

        # 4. Hierarchical Graph RAG Traversal
        graph_data: Dict[str, Any] = {}
        if use_graph_rag:
            graph_data = graph_rag_service.query_graph_context(
                tenant_id=tenant_id,
                query=query,
                max_hops=2,
                max_triples=8
            )

        # 5. Assemble Context Sections
        context_parts = []

        # Graph Context Section (if relations discovered)
        graph_summary = graph_data.get("subgraph_summary", "")
        if graph_summary:
            context_parts.append(graph_summary)

        # Document Chunks Section
        for chunk in final_chunks:
            payload = chunk.get("payload", {})
            text = payload.get("text", "")
            source = payload.get("source", "Unknown")
            page = payload.get("page", "N/A")
            score = chunk.get("crag_grade", chunk.get("relevance_score", chunk.get("score", 0)))
            
            context_part = f"[Source: {source}, Page: {page}, Confidence: {score:.2f}]\n{text}"
            context_parts.append(context_part)

        # CRAG Fallback Advisory Notice (if confidence was low)
        if crag_result and crag_result.system_advisory:
            context_parts.append(f"### Guardrail Note:\n{crag_result.system_advisory}")

        context_text = "\n\n".join(context_parts)
        trimmed_context = self._trim_context(context_text)

        # 6. Build LLM messages
        llm_messages = [
            {
                "role": "system",
                "content": self._build_system_prompt()
            },
            {
                "role": "user",
                "content": f"Context:\n{trimmed_context}\n\nQuestion: {query}"
            }
        ]

        return {
            "messages": llm_messages,
            "chunks": final_chunks,
            "sources": sources,
            "context_text": trimmed_context,
            "graph_rag": {
                "entities": graph_data.get("entities", []),
                "triples": graph_data.get("triples", []),
                "connected_documents": graph_data.get("connected_documents", [])
            },
            "crag": crag_result.to_dict() if crag_result else None
        }

    def _build_system_prompt(self) -> str:
        """Build system prompt for RAG"""
        return """You are Nexus Knowledge, an enterprise AI assistant backed by an Agentic, Self-Healing Knowledge Mesh.
Answer the user's question accurately using both the document context and the discovered knowledge graph relationships.
If the answer cannot be found in the context and a guardrail alert is present, transparently state that the knowledge base lacks sufficient ground truth rather than hallucinating.
Always cite sources and provide structured, insightful answers."""

    def _trim_context(self, context_text: str) -> str:
        """Trim context to fit within token limits"""
        max_chars = self.max_context_length * 4
        if len(context_text) <= max_chars:
            return context_text
        half_chars = max_chars // 2
        return context_text[:half_chars] + "\n...[trimmed for token limits]...\n" + context_text[-half_chars:]
