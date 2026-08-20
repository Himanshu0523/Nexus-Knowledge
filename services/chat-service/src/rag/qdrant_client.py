from typing import List, Dict, Any, Optional
import uuid
import os
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

class QdrantService:
    """Service for interacting with Qdrant vector database"""
    
    def __init__(self):
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", 6333))
        self.collection_name = os.getenv("QDRANT_COLLECTION", "document_chunks")
        self.vector_size = int(os.getenv("EMBEDDING_DIM", "384"))
        
        # Initialize client
        self.client = QdrantClient(host=self.host, port=self.port)
        
        # Ensure collection exists
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            print(f"Warning: Qdrant collection check skipped/deferred: {e}")
    
    def upsert_chunks(self, chunks: List[Dict[str, Any]], vectors: List[List[float]], tenant_id: str):
        """Insert chunks and vectors into Qdrant"""
        points = []
        
        for chunk, vector in zip(chunks, vectors):
            # Create unique point ID
            point_id = str(uuid.uuid4())
            
            # Prepare payload
            payload = {
                "document_id": chunk.get("metadata", {}).get("document_id"),
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "chunk_index": chunk["chunk_index"],
                "page": chunk.get("metadata", {}).get("page"),
                "source": chunk.get("metadata", {}).get("source"),
                "tenant_id": tenant_id,
                "metadata": chunk.get("metadata", {})
            }
            
            # Create point
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
            
            points.append(point)
        
        # Upsert points in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
        
        return len(points)
    
    def search(self, query_vector: List[float], tenant_id: str, limit: int = 20, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar chunks"""
        # Build filter
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id)
                )
            ]
        )
        
        # Add additional filters
        if filters:
            if "document_id" in filters:
                search_filter.must.append(
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=filters["document_id"])
                    )
                )
        
        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=search_filter
        )
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "payload": result.payload
            })
        
        return formatted_results
    
    def delete_document(self, document_id: str, tenant_id: str):
        """Delete all chunks for a document"""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id)
                    ),
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=tenant_id)
                    )
                ]
            )
        )
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection statistics"""
        info = self.client.get_collection(self.collection_name)
        return {
            "name": self.collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status
        }
    
    def health_check(self) -> bool:
        """Check if Qdrant is available"""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
