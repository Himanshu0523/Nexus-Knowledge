from typing import List, Dict, Any, Optional
import io
import os
from pypdf import PdfReader

class PDFParser:
    """Parse PDF documents and extract text with metadata"""
    
    def parse(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse PDF file and extract text with page numbers
        """
        try:
            # Create a file-like object from bytes
            pdf_file = io.BytesIO(file_bytes)
            
            # Read PDF
            reader = PdfReader(pdf_file)
            
            # Extract text from each page
            pages = []
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    pages.append({
                        "page_number": page_num,
                        "text": text.strip(),
                        "metadata": {
                            "page": page_num,
                            "source": filename
                        }
                    })
            
            return {
                "filename": filename,
                "file_type": "pdf",
                "pages": pages,
                "total_pages": len(reader.pages),
                "total_chars": sum(len(p["text"]) for p in pages),
                "status": "success",
                "error": None
            }
            
        except Exception as e:
            return {
                "filename": filename,
                "file_type": "pdf",
                "pages": [],
                "total_pages": 0,
                "total_chars": 0,
                "status": "error",
                "error": str(e)
            }
    
    def extract_metadata(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract PDF metadata"""
        try:
            pdf_file = io.BytesIO(file_bytes)
            reader = PdfReader(pdf_file)
            
            return {
                "metadata": reader.metadata,
                "num_pages": len(reader.pages),
                "is_encrypted": reader.is_encrypted
            }
        except Exception as e:
            return {
                "metadata": {},
                "num_pages": 0,
                "is_encrypted": False,
                "error": str(e)
            }
