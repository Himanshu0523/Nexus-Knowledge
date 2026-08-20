from typing import Dict, Any
import io
from docx import Document

class DOCXParser:
    """Parse DOCX documents and extract text"""
    
    def parse(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse DOCX file and extract text
        """
        try:
            # Create a file-like object from bytes
            docx_file = io.BytesIO(file_bytes)
            
            # Read document
            doc = Document(docx_file)
            
            # Extract text from paragraphs
            paragraphs = []
            for para in doc.paragraphs:
                if para.text and para.text.strip():
                    paragraphs.append(para.text.strip())
            
            # Join paragraphs into pages (approximate)
            # For DOCX, we don't have real pages, so we group paragraphs
            text = "\n\n".join(paragraphs)
            pages = [{
                "page_number": 1,
                "text": text,
                "metadata": {
                    "page": None,
                    "source": filename
                }
            }]
            
            return {
                "filename": filename,
                "file_type": "docx",
                "pages": pages if text else [],
                "total_pages": 1,
                "total_chars": len(text),
                "status": "success",
                "error": None
            }
            
        except Exception as e:
            return {
                "filename": filename,
                "file_type": "docx",
                "pages": [],
                "total_pages": 0,
                "total_chars": 0,
                "status": "error",
                "error": str(e)
            }
