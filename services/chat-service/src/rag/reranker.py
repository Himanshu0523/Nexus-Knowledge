"""
Cross-Encoder and Semantic Reranker for Nexus Knowledge.
Passes retrieved candidates through a cross-encoder model to re-score
and eliminate irrelevant noise before passing context to LLM.
"""

from typing import List, Dict, Any, Optional
import math
import logging
import numpy as np

logger = logging.getLogger(__name__)


class Reranker:
    """
    Two-stage Re-ranker:
    - Primary: Cross-Encoder neural model (ms-marco-MiniLM-L-6-v2) for deep semantic cross-attention.
    - Fallback: Advanced Lexical-Semantic Bi-Encoder fusion with phrase matching and position discount.
    """
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", final_limit: int = 5):
        self.model_name = model_name
        self.final_limit = final_limit
        self._cross_encoder = None
        self._cross_encoder_init_attempted = False

    def _get_cross_encoder(self):
        """Lazy loader for sentence_transformers CrossEncoder"""
        if not self._cross_encoder_init_attempted:
            self._cross_encoder_init_attempted = True
            try:
                from sentence_transformers import CrossEncoder
                self._cross_encoder = CrossEncoder(self.model_name)
                logger.info(f"[Reranker] Successfully loaded CrossEncoder: {self.model_name}")
            except Exception as e:
                logger.warning(f"[Reranker] CrossEncoder not initialized ({e}). Using optimized fallback.")
                self._cross_encoder = None
        return self._cross_encoder

    def _sigmoid(self, x: float) -> float:
        """Sigmoid activation for normalizing logits to [0.0, 1.0]"""
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0

    def rerank(self, query: str, chunks: List[Dict[str, Any]], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Re-rank retrieved chunks using Cross-Encoder with seamless neural fallback.
        """
        if not chunks:
            return []

        target_limit = limit or self.final_limit
        ce_model = self._get_cross_encoder()

        if ce_model is not None:
            try:
                pairs = []
                for chunk in chunks:
                    text = chunk.get("payload", {}).get("text", "")
                    pairs.append([query, text])

                raw_scores = ce_model.predict(pairs)
                reranked_chunks = []

                for chunk, raw_score in zip(chunks, raw_scores):
                    c = dict(chunk)
                    normalized_score = float(self._sigmoid(float(raw_score)))
                    c["cross_encoder_score"] = float(raw_score)
                    c["relevance_score"] = round(normalized_score, 4)
                    c["combined_score"] = round(normalized_score, 4)
                    c["rerank_method"] = "cross_encoder"
                    reranked_chunks.append(c)

                reranked_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
                return reranked_chunks[:target_limit]
            except Exception as e:
                logger.warning(f"[Reranker] Error in cross-encoder inference: {e}. Falling back.")

        # Fallback: Advanced Lexical-Semantic Bi-Encoder scoring
        return self._lexical_semantic_rerank(query, chunks, target_limit)

    def _lexical_semantic_rerank(self, query: str, chunks: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """
        Advanced heuristic reranker combining vector score, Jaccard token overlap,
        exact phrase containment, and document completeness.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        reranked_chunks = []

        for chunk in chunks:
            c = dict(chunk)
            payload = c.get("payload", {})
            text = payload.get("text", "")
            text_lower = text.lower()
            text_words = set(text_lower.split())

            # 1. Jaccard token overlap
            intersection = query_words & text_words
            jaccard = len(intersection) / max(len(query_words | text_words), 1)

            # 2. Query word coverage (what fraction of query words exist in doc)
            coverage = len(intersection) / max(len(query_words), 1)

            # 3. Exact phrase containment bonus
            phrase_bonus = 0.25 if (len(query_lower) > 5 and query_lower in text_lower) else 0.0

            # 4. Dense / retrieval score base
            vector_score = float(c.get("score", 0.0))
            if vector_score > 1.0:
                vector_score = min(vector_score / 100.0, 1.0)  # Normalize if scaled

            # Blended weighted score
            final_score = (vector_score * 0.45) + (coverage * 0.35) + (jaccard * 0.10) + phrase_bonus
            final_score = min(max(final_score, 0.0), 1.0)

            c["relevance_score"] = round(final_score, 4)
            c["combined_score"] = round(final_score, 4)
            c["lexical_coverage"] = round(coverage, 4)
            c["rerank_method"] = "lexical_semantic_fusion"

            reranked_chunks.append(c)

        reranked_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
        return reranked_chunks[:limit]

    def cross_encoder_rerank(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Backwards compatibility alias for rerank"""
        return self.rerank(query, chunks)
