"""
Corrective RAG (CRAG) & Self-Correction Evaluation Engine.
Implements automated retrieval evaluation, confidence grading, query reformulation,
and external fallback loops to prevent hallucinations and self-heal failed retrievals.
"""

from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class CRAGAction(str, Enum):
    CORRECT = "correct"            # High confidence (>= 0.75): context is sound
    AMBIGUOUS = "ambiguous"        # Medium confidence (0.40 - 0.74): needs query reformulation & re-retrieval
    INCORRECT = "incorrect"        # Low confidence (< 0.40): fallback to web search or transparent refusal


class CRAGResult:
    """Encapsulates the decision and transformed context from the CRAG evaluation loop."""
    def __init__(
        self,
        action: CRAGAction,
        confidence_score: float,
        chunks: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        reformulated_query: Optional[str] = None,
        fallback_used: bool = False,
        system_advisory: Optional[str] = None
    ):
        self.action = action
        self.confidence_score = round(confidence_score, 4)
        self.chunks = chunks
        self.sources = sources
        self.reformulated_query = reformulated_query
        self.fallback_used = fallback_used
        self.system_advisory = system_advisory

    def to_dict(self) -> Dict[str, Any]:
        return {
            "crag_action": self.action.value,
            "confidence_score": self.confidence_score,
            "chunks_count": len(self.chunks),
            "sources": self.sources,
            "reformulated_query": self.reformulated_query,
            "fallback_used": self.fallback_used,
            "system_advisory": self.system_advisory
        }


class CorrectiveRAGEvaluator:
    """
    Evaluator model that grades retrieved document chunks and triggers self-correction loops.
    """

    def __init__(
        self,
        correct_threshold: float = 0.75,
        incorrect_threshold: float = 0.40,
        min_chunk_relevance: float = 0.35
    ):
        self.correct_threshold = correct_threshold
        self.incorrect_threshold = incorrect_threshold
        self.min_chunk_relevance = min_chunk_relevance

    def grade_chunk_relevance(self, query: str, chunk: Dict[str, Any]) -> float:
        """
        Grade relevance score for an individual chunk.
        Uses cross-encoder or combined relevance score, supplemented with query term coverage.
        """
        base_score = float(chunk.get("relevance_score", chunk.get("combined_score", chunk.get("score", 0.0))))
        if base_score > 1.0:
            base_score = min(base_score / 100.0, 1.0)

        # Lexical term coverage inspection
        payload = chunk.get("payload", {})
        text = (payload.get("text", "")).lower()
        query_words = set(re.findall(r"\b\w{3,}\b", query.lower()))

        if not query_words:
            return base_score

        covered = sum(1 for w in query_words if w in text)
        coverage_ratio = covered / len(query_words)

        # Blended evaluation grade
        grade = (base_score * 0.6) + (coverage_ratio * 0.4)
        return min(max(grade, 0.0), 1.0)

    def evaluate_retrieval(
        self,
        query: str,
        chunks: List[Dict[str, Any]]
    ) -> Tuple[CRAGAction, float, List[Dict[str, Any]]]:
        """
        Evaluate retrieved chunks, strip low-relevance noise, and determine CRAG action.
        """
        if not chunks:
            return CRAGAction.INCORRECT, 0.0, []

        graded_chunks = []
        scores = []

        for chunk in chunks:
            grade = self.grade_chunk_relevance(query, chunk)
            c = dict(chunk)
            c["crag_grade"] = round(grade, 4)
            if grade >= self.min_chunk_relevance:
                graded_chunks.append(c)
                scores.append(grade)

        if not graded_chunks:
            return CRAGAction.INCORRECT, 0.0, []

        # Top chunk weighted average confidence
        top_k_scores = sorted(scores, reverse=True)[:3]
        confidence = sum(top_k_scores) / len(top_k_scores)

        if confidence >= self.correct_threshold:
            action = CRAGAction.CORRECT
        elif confidence >= self.incorrect_threshold:
            action = CRAGAction.AMBIGUOUS
        else:
            action = CRAGAction.INCORRECT

        return action, confidence, graded_chunks

    def reformulate_query(self, query: str) -> str:
        """
        Self-healing step for AMBIGUOUS retrieval:
        Expands keywords, removes conversational filler, and constructs high-density search terms.
        """
        filler_words = {
            "what", "is", "the", "are", "how", "do", "does", "our", "can", "you",
            "tell", "me", "about", "according", "to", "document", "pdf", "file",
            "please", "explain", "give", "show"
        }
        words = re.findall(r"\b\w+\b", query)
        core_terms = [w for w in words if w.lower() not in filler_words and len(w) > 2]

        if not core_terms:
            return query

        expanded_query = " ".join(core_terms)
        logger.info(f"[CRAG] Reformulated query: '{query}' -> '{expanded_query}'")
        return expanded_query

    async def _try_external_web_search(self, query: str) -> Optional[str]:
        """Attempt external search fallback when relevance drops below threshold."""
        try:
            import os
            import httpx
            tavily_key = os.getenv("TAVILY_API_KEY")
            if tavily_key:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={"query": query, "api_key": tavily_key, "max_results": 2}
                    )
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        snippets = [r.get("content", "") for r in results if r.get("content")]
                        if snippets:
                            return "\n".join(snippets)
        except Exception as e:
            logger.debug(f"[CRAG] External web search fallback skipped: {e}")
        return None

    async def execute_crag_loop(
        self,
        query: str,
        initial_chunks: List[Dict[str, Any]],
        retriever_callable,
        tenant_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> CRAGResult:
        """
        Executes the complete Corrective RAG state machine:
        1. Grades retrieved chunks.
        2. If CORRECT (>= 0.75): proceeds directly.
        3. If AMBIGUOUS (0.40 - 0.74): reformulates query and re-retrieves, blending results.
        4. If INCORRECT (< 0.40): triggers external fallback / clear refusal notice.
        """
        action, confidence, filtered_chunks = self.evaluate_retrieval(query, initial_chunks)
        reformulated_query = None
        fallback_used = False
        system_advisory = None

        logger.info(f"[CRAG] Initial evaluation: Action={action.value}, Confidence={confidence:.4f}, ValidChunks={len(filtered_chunks)}")

        # ── State 1: AMBIGUOUS -> Query Reformulation & Secondary Retrieval ──
        if action == CRAGAction.AMBIGUOUS and retriever_callable:
            reformulated_query = self.reformulate_query(query)
            try:
                secondary_chunks = await retriever_callable(
                    query=reformulated_query,
                    tenant_id=tenant_id,
                    filters=filters
                )
                # Combine & deduplicate chunks
                seen_ids = set()
                merged_chunks = []
                for c in filtered_chunks + secondary_chunks:
                    cid = c.get("payload", {}).get("chunk_id") or str(c.get("id"))
                    if cid not in seen_ids:
                        seen_ids.add(cid)
                        merged_chunks.append(c)

                # Re-evaluate merged chunks
                re_action, re_conf, re_filtered = self.evaluate_retrieval(query, merged_chunks)
                if re_conf > confidence:
                    filtered_chunks = re_filtered
                    confidence = re_conf
                    action = re_action
                    system_advisory = f"[CRAG Self-Correction] Retrieval enhanced via query reformulation: '{reformulated_query}'."
            except Exception as e:
                logger.warning(f"[CRAG] Secondary retrieval loop failed: {e}")

        # ── State 2: INCORRECT -> External Fallback & Anti-Hallucination Guard ──
        if action == CRAGAction.INCORRECT:
            fallback_used = True
            external_info = await self._try_external_web_search(query)
            if external_info:
                system_advisory = (
                    f"[CRAG External Web Search Fallback] Enterprise KB relevance score was below {self.correct_threshold:.2f}. "
                    f"External grounding retrieved:\n{external_info}"
                )
            else:
                system_advisory = (
                    f"[CRAG Guardrail Alert] Enterprise knowledge base relevance score ({confidence:.2f}) is below "
                    f"the required threshold ({self.correct_threshold:.2f}). Please clarify your question or specify documents."
                )

        # Build formatted source citations
        sources = []
        for chunk in filtered_chunks:
            payload = chunk.get("payload", {})
            sources.append({
                "document": payload.get("source", "Unknown"),
                "page": payload.get("page", "N/A"),
                "relevance_score": chunk.get("crag_grade", chunk.get("score", 0.0)),
                "chunk_id": payload.get("chunk_id")
            })

        return CRAGResult(
            action=action,
            confidence_score=confidence,
            chunks=filtered_chunks,
            sources=sources,
            reformulated_query=reformulated_query,
            fallback_used=fallback_used,
            system_advisory=system_advisory
        )


# Global singleton instance
crag_evaluator = CorrectiveRAGEvaluator(correct_threshold=0.75, incorrect_threshold=0.40)


async def evaluate_retrieval_confidence(query: str, chunks: List[Dict[str, Any]]) -> float:
    """
    Lightweight async judge function that takes the user's query and the retrieved top chunks,
    and outputs a calibrated confidence score between 0.0 and 1.0.

    - Score >= 0.75: High confidence, proceeds directly to prompt construction.
    - Score < 0.75: Low/ambiguous confidence, triggers query reformulation or fallback.
    """
    if not chunks:
        return 0.0
    _, confidence, _ = crag_evaluator.evaluate_retrieval(query, chunks)
    return round(float(confidence), 4)
