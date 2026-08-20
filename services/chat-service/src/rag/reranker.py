from typing import List, Dict, Any
import numpy as np

class Reranker:
    """Re-rank retrieved chunks for better relevance"""
    
    def __init__(self):
        self.use_cross_encoder = False
        self.final_limit = 5
    
    def rerank(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Re-rank chunks based on relevance to query"""
        if not chunks:
            return []
        
        # Simple re-ranking based on score and text overlap
        reranked_chunks = []
        
        for chunk in chunks:
            # Calculate additional relevance signals
            text = chunk.get("payload", {}).get("text", "")
            
            # Calculate lexical overlap
            query_words = set(query.lower().split())
            text_words = set(text.lower().split())
            overlap_score = len(query_words & text_words) / max(len(query_words), 1)
            
            # Combine scores (vector similarity + lexical overlap)
            vector_score = chunk.get("score", 0)
            combined_score = (vector_score * 0.7) + (overlap_score * 0.3)
            
            chunk["combined_score"] = combined_score
            chunk["vector_score"] = vector_score
            chunk["overlap_score"] = overlap_score
            
            reranked_chunks.append(chunk)
        
        # Sort by combined score
        reranked_chunks.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Return top chunks
        return reranked_chunks[:self.final_limit]
    
    def cross_encoder_rerank(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Re-rank using cross-encoder (if available)"""
        try:
            from sentence_transformers import CrossEncoder
            
            # Load model (cache it)
            if not hasattr(self, '_cross_encoder'):
                self._cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            
            # Prepare pairs
            pairs = []
            for chunk in chunks:
                text = chunk.get("payload", {}).get("text", "")
                pairs.append([query, text])
            
            # Get scores
            scores = self._cross_encoder.predict(pairs)
            
            # Add scores to chunks
            for chunk, score in zip(chunks, scores):
                chunk["cross_encoder_score"] = float(score)
                chunk["combined_score"] = float(score)
            
            # Sort by score
            chunks.sort(key=lambda x: x["cross_encoder_score"], reverse=True)
            
            return chunks[:self.final_limit]
            
        except ImportError:
            # Fallback to simple reranking
            return self.rerank(query, chunks)
