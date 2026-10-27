"""
Hybrid Search Retriever with Reciprocal Rank Fusion (RRF).
Fuses dense semantic vector search (Qdrant) with sparse lexical BM25 search
to guarantee high-recall keyword matching (technical codes, IDs, exact terms)
alongside conceptual semantic search.
"""

from typing import List, Dict, Any, Optional
import math
import logging
import re
from .qdrant_client import QdrantService
from .embeddings import EmbeddingService

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False

logger = logging.getLogger(__name__)


class HybridCorpusIndex:
    """In-memory BM25 lexical index keyed by tenant_id"""
    def __init__(self):
        self._tenant_chunks: Dict[str, List[Dict[str, Any]]] = {}
        self._tenant_bm25: Dict[str, Any] = {}

    def tokenize(self, text: str) -> List[str]:
        """Simple tokenization stripping punctuation and lowercasing"""
        return re.findall(r"\b\w+\b", text.lower())

    def add_chunk(self, tenant_id: str, chunk: Dict[str, Any]):
        """Register or update a chunk in the tenant BM25 index"""
        if tenant_id not in self._tenant_chunks:
            self._tenant_chunks[tenant_id] = []
        
        # Check if already present by chunk_id
        chunk_id = chunk.get("chunk_id")
        existing_idx = None
        for i, c in enumerate(self._tenant_chunks[tenant_id]):
            if c.get("chunk_id") == chunk_id:
                existing_idx = i
                break

        if existing_idx is not None:
            self._tenant_chunks[tenant_id][existing_idx] = chunk
        else:
            self._tenant_chunks[tenant_id].append(chunk)

        # Invalidate BM25 model for tenant so it is rebuilt on next search
        if tenant_id in self._tenant_bm25:
            del self._tenant_bm25[tenant_id]

    def add_chunks_batch(self, tenant_id: str, chunks: List[Dict[str, Any]]):
        for chunk in chunks:
            self.add_chunk(tenant_id, chunk)

    def _ensure_bm25(self, tenant_id: str):
        if not _BM25_AVAILABLE:
            return
        if tenant_id not in self._tenant_bm25 and tenant_id in self._tenant_chunks:
            chunks = self._tenant_chunks[tenant_id]
            corpus = [self.tokenize(c.get("text", "") or c.get("payload", {}).get("text", "")) for c in chunks]
            if corpus:
                self._tenant_bm25[tenant_id] = BM25Okapi(corpus)

    def search_bm25(self, tenant_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Perform BM25 search over tenant corpus"""
        if tenant_id not in self._tenant_chunks or not self._tenant_chunks[tenant_id]:
            return []

        tokens = self.tokenize(query)
        if not tokens:
            return []

        if _BM25_AVAILABLE:
            self._ensure_bm25(tenant_id)
            bm25 = self._tenant_bm25.get(tenant_id)
            if not bm25:
                return []
            scores = bm25.get_scores(tokens)
        else:
            # Fallback TF-IDF overlap if rank_bm25 is missing
            query_set = set(tokens)
            scores = []
            for c in self._tenant_chunks[tenant_id]:
                text = (c.get("text", "") or c.get("payload", {}).get("text", "")).lower()
                c_tokens = self.tokenize(text)
                overlap = sum(1 for t in c_tokens if t in query_set)
                scores.append(overlap / max(len(c_tokens), 1))

        # Rank chunks by score
        chunks = self._tenant_chunks[tenant_id]
        scored_pairs = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
        results = []
        for chunk, score in scored_pairs[:limit]:
            text = (chunk.get("text", "") or chunk.get("payload", {}).get("text", "")).lower()
            overlap = any(t in text for t in tokens)
            if score > 0 or overlap:
                effective_score = max(float(score), 0.5 if overlap else 0.0)
                payload = chunk.get("payload") or {
                    "text": chunk.get("text", ""),
                    "chunk_id": chunk.get("chunk_id"),
                    "source": chunk.get("metadata", {}).get("source", "Unknown"),
                    "page": chunk.get("metadata", {}).get("page", 1)
                }
                results.append({
                    "id": chunk.get("chunk_id", str(len(results))),
                    "score": effective_score,
                    "payload": payload,
                    "retrieval_mode": "bm25_lexical"
                })
        return results


# Global singleton lexical index
lexical_corpus_index = HybridCorpusIndex()


class Retriever:
    """
    Advanced Multi-Tenant Retriever supporting:
    1. Dense Semantic Vector Retrieval (Qdrant)
    2. Sparse Lexical Search (BM25)
    3. Reciprocal Rank Fusion (RRF) Blending
    """

    def __init__(self):
        self.qdrant = QdrantService()
        self.embeddings = EmbeddingService()
        self.retrieval_limit = 20  # Retrieve top 20 for reranking
        self.rrf_k = 60            # Standard constant for RRF damping
        self.dense_weight = 0.6    # Weight for dense vector search
        self.sparse_weight = 0.4   # Weight for BM25 lexical search

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        filters: Optional[Dict[str, Any]] = None,
        use_hybrid: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks using Hybrid Dense + BM25 Reciprocal Rank Fusion.
        """
        # Step 1: Dense Semantic Search via Qdrant
        dense_results: List[Dict[str, Any]] = []
        try:
            query_vector = await self.embeddings.generate_embedding(query)
            dense_results = self.qdrant.search(
                query_vector=query_vector,
                tenant_id=tenant_id,
                limit=self.retrieval_limit,
                filters=filters
            )
        except Exception as e:
            logger.warning(f"[Retriever] Dense vector retrieval encountered issue: {e}")

        # If hybrid is disabled or no BM25 corpus indexed yet, return dense results
        if not use_hybrid:
            return dense_results

        # Step 2: Sparse Lexical Search via BM25
        sparse_results = lexical_corpus_index.search_bm25(
            tenant_id=tenant_id,
            query=query,
            limit=self.retrieval_limit
        )

        if not sparse_results:
            return dense_results

        # Step 3: Reciprocal Rank Fusion (RRF)
        # RRF(d) = sum( weight / (k + rank_i(d)) )
        fused_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Dict[str, Any]] = {}
        dense_ranks: Dict[str, int] = {}
        sparse_ranks: Dict[str, int] = {}

        # Process Dense Rankings
        for rank, item in enumerate(dense_results, start=1):
            chunk_id = item.get("payload", {}).get("chunk_id") or str(item.get("id"))
            chunk_map[chunk_id] = item
            dense_ranks[chunk_id] = rank
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + (self.dense_weight / (self.rrf_k + rank))

        # Process Sparse Rankings
        for rank, item in enumerate(sparse_results, start=1):
            chunk_id = item.get("payload", {}).get("chunk_id") or str(item.get("id"))
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = item
            sparse_ranks[chunk_id] = rank
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + (self.sparse_weight / (self.rrf_k + rank))

        # Sort by fused RRF score
        fused_items: List[Dict[str, Any]] = []
        for chunk_id, rrf_score in sorted(fused_scores.items(), key=lambda x: x[1], reverse=True):
            item = dict(chunk_map[chunk_id])
            item["rrf_score"] = float(rrf_score)
            item["dense_rank"] = dense_ranks.get(chunk_id)
            item["sparse_rank"] = sparse_ranks.get(chunk_id)
            item["score"] = float(rrf_score * 100.0)  # Normalized display score
            item["retrieval_mode"] = "hybrid_rrf"
            fused_items.append(item)

        return fused_items[:self.retrieval_limit]

    async def retrieve_with_threshold(
        self,
        query: str,
        tenant_id: str,
        threshold: float = 0.5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks above a similarity or fusion threshold"""
        results = await self.retrieve(query, tenant_id, filters)
        
        filtered_results = [
            result for result in results 
            if result.get("score", 0) >= threshold
        ]
        
        return filtered_results
