from typing import List, Dict, Any
import re
import uuid

class TextCleaner:
    """Clean extracted text from documents"""
    
    def __init__(self):
        self.patterns = {
            'page_numbers': re.compile(r'^\s*\d+\s*$', re.MULTILINE),
            'headers': re.compile(r'^\s*(?:CHAPTER|Chapter|SECTION|Section)\s+\d+.*$', re.MULTILINE),
            'extra_whitespace': re.compile(r'\s+'),
            'repeated_newlines': re.compile(r'\n{3,}'),
        }
    
    def clean(self, text: str) -> str:
        """Clean text by removing unwanted patterns"""
        # Remove page numbers
        text = self.patterns['page_numbers'].sub('', text)
        
        # Remove extra whitespace
        text = self.patterns['extra_whitespace'].sub(' ', text)
        
        # Remove repeated newlines
        text = self.patterns['repeated_newlines'].sub('\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text

class TextChunker:
    """Split text into overlapping chunks"""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.cleaner = TextCleaner()
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Split text into chunks with metadata"""
        # Clean text first
        text = self.cleaner.clean(text)
        
        if not text:
            return []
        
        # Split into words
        words = text.split()
        chunks = []
        chunk_index = 0
        
        # Create chunks with overlap
        i = 0
        while i < len(words):
            # Get chunk words
            chunk_words = words[i:i + self.chunk_size]
            
            if not chunk_words:
                break
            
            # Join words into chunk text
            chunk_text = ' '.join(chunk_words)
            
            # Create chunk metadata
            chunk_id = f"chunk_{uuid.uuid4().hex[:10]}"
            chunk = {
                "chunk_id": chunk_id,
                "text": chunk_text,
                "chunk_index": chunk_index,
                "start_word": i,
                "end_word": min(i + self.chunk_size, len(words)),
                "metadata": metadata or {}
            }
            
            chunks.append(chunk)
            chunk_index += 1
            
            # Move to next chunk start (with overlap)
            i += self.chunk_size - self.overlap
            
            # Break if we've reached the end
            if i >= len(words):
                break
        
        # Update total chunks in metadata
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)
        
        return chunks
    
    def chunk_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk entire document"""
        all_chunks = []
        
        for page in document.get("pages", []):
            page_chunks = self.chunk_text(
                page["text"],
                metadata={
                    "page": page.get("page_number"),
                    "source": page.get("metadata", {}).get("source"),
                    "document_id": document.get("document_id")
                }
            )
            all_chunks.extend(page_chunks)
        
        return all_chunks

class SentenceChunker:
    """Alternative chunker that splits by sentences"""
    
    def __init__(self, max_sentences: int = 5, overlap_sentences: int = 1):
        self.max_sentences = max_sentences
        self.overlap_sentences = overlap_sentences
        self.cleaner = TextCleaner()
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Split text into sentence-based chunks"""
        # Clean text
        text = self.cleaner.clean(text)
        
        if not text:
            return []
        
        # Split into sentences (simple approach)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        chunk_index = 0
        i = 0
        
        while i < len(sentences):
            # Get chunk sentences
            chunk_sentences = sentences[i:i + self.max_sentences]
            
            if not chunk_sentences:
                break
            
            # Join sentences into chunk
            chunk_text = ' '.join(chunk_sentences)
            
            # Create chunk
            chunk_id = f"chunk_{uuid.uuid4().hex[:10]}"
            chunk = {
                "chunk_id": chunk_id,
                "text": chunk_text,
                "chunk_index": chunk_index,
                "start_sentence": i,
                "end_sentence": min(i + self.max_sentences, len(sentences)),
                "metadata": metadata or {}
            }
            
            chunks.append(chunk)
            chunk_index += 1
            
            # Move with overlap
            i += self.max_sentences - self.overlap_sentences
            
            if i >= len(sentences):
                break
        
        # Update total chunks
        for chunk in chunks:
            chunk["metadata"]["total_chunks"] = len(chunks)
        
        return chunks
