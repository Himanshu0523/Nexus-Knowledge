from typing import List, Dict, Any
import numpy as np
import hashlib
import os
import httpx
import json

class EmbeddingService:
    """Generate embeddings for text chunks"""
    
    def __init__(self):
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "mock")
        self.embedding_dim = int(os.getenv("EMBEDDING_DIM", "384"))
        self.api_key = os.getenv("EMBEDDING_API_KEY", "")
        self.api_url = os.getenv("EMBEDDING_API_URL", "")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if self.embedding_model == "mock":
            return self._mock_embedding(text)
        elif self.embedding_model == "openai":
            return await self._openai_embedding(text)
        elif self.embedding_model == "huggingface":
            return await self._huggingface_embedding(text)
        else:
            return self._mock_embedding(text)
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings
    
    def _mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding (for testing)"""
        # Create a deterministic embedding based on text hash
        text_hash = hashlib.sha256(text.encode()).digest()
        
        # Convert hash to seed for random number generator
        seed = int.from_bytes(text_hash[:4], byteorder='big')
        np.random.seed(seed)
        
        # Generate embedding
        embedding = np.random.randn(self.embedding_dim)
        
        # Normalize
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding.tolist()
    
    def _sentence_transformer_embedding(self, text: str) -> List[float]:
        """Generate embedding using sentence-transformers (if installed)"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Load model (cache it)
            if not hasattr(self, '_model'):
                self._model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Generate embedding
            embedding = self._model.encode(text)
            
            return embedding.tolist()
        except ImportError:
            return self._mock_embedding(text)
    
    async def _openai_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "text-embedding-ada-002",
                    "input": text
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["data"][0]["embedding"]
            else:
                return self._mock_embedding(text)
    
    async def _huggingface_embedding(self, text: str) -> List[float]:
        """Generate embedding using HuggingFace API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={"inputs": text},
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return self._mock_embedding(text)
