from typing import Dict, Any, List
import asyncio
import uuid
import logging
from datetime import datetime
import os

from parsers import DocumentParserFactory
from .chunking import TextChunker
from .embeddings import EmbeddingService
from .qdrant_client import QdrantService
from .retriever import lexical_corpus_index
from .graph_rag import graph_rag_service

logger = logging.getLogger(__name__)

class IngestionPipeline:
    """Complete document ingestion pipeline with Hybrid BM25 indexing and Knowledge Graph extraction"""
    
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
            
            # Step 3: Generate dense embeddings
            chunk_texts = [chunk["text"] for chunk in chunks]
            vectors = await self.embeddings.generate_embeddings(chunk_texts)
            
            # Step 4: Store in Qdrant (Dense Vectors)
            points_created = self.qdrant.upsert_chunks(chunks, vectors, tenant_id)

            # Step 5: Index in BM25 Lexical Corpus (Sparse Search)
            lexical_corpus_index.add_chunks_batch(tenant_id, chunks)

            # Step 6: Construct Knowledge Graph (Hierarchical Graph RAG)
            graph_entities_total = 0
            graph_triples_total = 0
            for chunk in chunks:
                g_res = graph_rag_service.ingest_chunk_to_graph(
                    tenant_id=tenant_id,
                    document_id=document_id,
                    chunk_id=chunk["chunk_id"],
                    text=chunk["text"],
                    metadata=chunk.get("metadata", {})
                )
                graph_entities_total += g_res.get("entities_found", 0)
                graph_triples_total += g_res.get("triples_found", 0)
            
            logger.info(
                f"[IngestionPipeline] Document '{document_id}' processed: "
                f"{points_created} vector points, {graph_entities_total} entities, {graph_triples_total} graph triples"
            )

            return {
                "status": "completed",
                "document_id": document_id,
                "filename": filename,
                "chunks_created": points_created,
                "file_type": file_type,
                "total_pages": parsed_document.get("total_pages", 1),
                "graph_entities": graph_entities_total,
                "graph_triples": graph_triples_total
            }
            
        except Exception as e:
            logger.error(f"[IngestionPipeline] Error ingesting {filename}: {e}")
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
