from typing import List, Dict, Any, Optional
from .qdrant_client import QdrantService
from .embeddings import EmbeddingService

class Retriever:
    """Retrieve relevant chunks from Qdrant"""
    
    def __init__(self):
        self.qdrant = QdrantService()
        self.embeddings = EmbeddingService()
        self.retrieval_limit = 20  # Retrieve top 20 for reranking
    
    async def retrieve(self, query: str, tenant_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a query"""
        # Generate query embedding
        query_vector = await self.embeddings.generate_embedding(query)
        
        # Search Qdrant
        results = self.qdrant.search(
            query_vector=query_vector,
            tenant_id=tenant_id,
            limit=self.retrieval_limit,
            filters=filters
        )
        
        return results
    
    async def retrieve_with_threshold(self, query: str, tenant_id: str, threshold: float = 0.5, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve chunks above a similarity threshold"""
        results = await self.retrieve(query, tenant_id, filters)
        
        # Filter by threshold
        filtered_results = [
            result for result in results 
            if result["score"] >= threshold
        ]
        
        return filtered_results
