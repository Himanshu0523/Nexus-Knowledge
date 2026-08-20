from typing import List, Dict, Any
from .retriever import Retriever
from .reranker import Reranker

class RAGContextBuilder:
    """Build context for LLM using retrieved chunks"""
    
    def __init__(self):
        self.retriever = Retriever()
        self.reranker = Reranker()
        self.max_context_length = 4000
    
    async def build_context(self, query: str, tenant_id: str, knowledge_base_id: str = None) -> Dict[str, Any]:
        """Build RAG context for LLM"""
        # Retrieve relevant chunks
        filters = {}
        if knowledge_base_id:
            filters["knowledge_base_id"] = knowledge_base_id
        
        chunks = await self.retriever.retrieve(query, tenant_id, filters)
        
        # Re-rank chunks
        reranked_chunks = self.reranker.rerank(query, chunks)
        
        # Build context text
        context_parts = []
        sources = []
        
        for chunk in reranked_chunks:
            payload = chunk.get("payload", {})
            text = payload.get("text", "")
            source = payload.get("source", "Unknown")
            page = payload.get("page", "N/A")
            score = chunk.get("combined_score", chunk.get("score", 0))
            
            # Format context chunk
            context_part = f"[Source: {source}, Page: {page}, Relevance: {score:.2f}]\n{text}"
            context_parts.append(context_part)
            
            # Add to sources
            sources.append({
                "document": source,
                "page": page,
                "relevance_score": score,
                "chunk_id": payload.get("chunk_id")
            })
        
        # Build full context
        context_text = "\n\n".join(context_parts)
        
        # Build LLM messages
        llm_messages = [
            {
                "role": "system",
                "content": self._build_system_prompt()
            },
            {
                "role": "user",
                "content": f"Context:\n{context_text}\n\nQuestion: {query}"
            }
        ]
        
        return {
            "messages": llm_messages,
            "chunks": reranked_chunks,
            "sources": sources,
            "context_text": context_text
        }
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for RAG"""
        return """You are a helpful AI assistant with access to a knowledge base.
Answer the user's question based on the provided context.
If the answer cannot be found in the context, say "I don't have enough information in the connected knowledge base to answer this question."
Always cite sources when providing information from the context.
Be concise and accurate in your responses."""
    
    def _trim_context(self, context_text: str) -> str:
        """Trim context to fit within token limits"""
        # Simple character-based trimming (1 token ≈ 4 characters)
        max_chars = self.max_context_length * 4
        
        if len(context_text) <= max_chars:
            return context_text
        
        # Trim from the middle (keep beginning and end)
        half_chars = max_chars // 2
        return context_text[:half_chars] + "\n...[truncated]...\n" + context_text[-half_chars:]
