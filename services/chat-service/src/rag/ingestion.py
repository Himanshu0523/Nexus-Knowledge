from typing import Dict, Any, List
import asyncio
import uuid
from datetime import datetime
import os

from parsers import DocumentParserFactory
from .chunking import TextChunker
from .embeddings import EmbeddingService
from .qdrant_client import QdrantService

class IngestionPipeline:
    """Complete document ingestion pipeline"""
    
    def __init__(self):
        self.chunker = TextChunker(chunk_size=500, overlap=50)
        self.embeddings = EmbeddingService()
        self.qdrant = QdrantService()
    
    async def process_document(self, file_bytes: bytes, filename: str, document_id: str, tenant_id: str) -> Dict[str, Any]:
        """Process a document through the entire ingestion pipeline"""
        try:
            # Step 1: Parse document
            file_type = DocumentParserFactory.get_file_type(filename)
            parser = DocumentParserFactory.get_parser(file_type)
            parsed_document = parser.parse(file_bytes, filename)
            
            if parsed_document["status"] == "error":
                return {
                    "status": "failed",
                    "error": parsed_document["error"],
                    "document_id": document_id
                }
            
            # Step 2: Chunk document
            parsed_document["document_id"] = document_id
            chunks = self.chunker.chunk_document(parsed_document)
            
            if not chunks:
                return {
                    "status": "failed",
                    "error": "No text extracted from document",
                    "document_id": document_id
                }
            
            # Step 3: Generate embeddings
            chunk_texts = [chunk["text"] for chunk in chunks]
            vectors = await self.embeddings.generate_embeddings(chunk_texts)
            
            # Step 4: Store in Qdrant
            points_created = self.qdrant.upsert_chunks(chunks, vectors, tenant_id)
            
            return {
                "status": "completed",
                "document_id": document_id,
                "filename": filename,
                "chunks_created": points_created,
                "file_type": file_type,
                "total_pages": parsed_document.get("total_pages", 1)
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "document_id": document_id
            }
    
    async def process_documents_batch(self, documents: List[Dict[str, Any]], tenant_id: str) -> List[Dict[str, Any]]:
        """Process multiple documents"""
        results = []
        
        for doc in documents:
            result = await self.process_document(
                file_bytes=doc["file_bytes"],
                filename=doc["filename"],
                document_id=doc["document_id"],
                tenant_id=tenant_id
            )
            results.append(result)
        
        return results
