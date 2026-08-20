from typing import Dict, Any
import io

class TextParser:
    """Parse plain text and markdown documents"""
    
    def parse(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse text file and extract content
        """
        try:
            # Decode bytes to text
            text = file_bytes.decode('utf-8')
            
            # Clean text
            text = text.strip()
            
            # Split into logical sections (by double newlines)
            sections = text.split('\n\n')
            
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
                "file_type": "text",
                "pages": pages if text else [],
                "total_pages": 1,
                "total_chars": len(text),
                "status": "success",
                "error": None
            }
            
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                text = file_bytes.decode('latin-1')
                return {
                    "filename": filename,
                    "file_type": "text",
                    "pages": [{"page_number": 1, "text": text, "metadata": {"source": filename}}],
                    "total_pages": 1,
                    "total_chars": len(text),
                    "status": "success",
                    "error": None
                }
            except Exception as e:
                return {
                    "filename": filename,
                    "file_type": "text",
                    "pages": [],
                    "total_pages": 0,
                    "total_chars": 0,
                    "status": "error",
                    "error": str(e)
                }
        except Exception as e:
            return {
                "filename": filename,
                "file_type": "text",
                "pages": [],
                "total_pages": 0,
                "total_chars": 0,
                "status": "error",
                "error": str(e)
            }
