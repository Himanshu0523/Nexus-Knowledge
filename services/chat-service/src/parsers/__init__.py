from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .text_parser import TextParser

class DocumentParserFactory:
    """Factory for document parsers"""
    
    @staticmethod
    def get_parser(file_type: str):
        """Get appropriate parser based on file type"""
        file_type = file_type.lower()
        
        if file_type == 'pdf':
            return PDFParser()
        elif file_type in ['docx', 'doc']:
            return DOCXParser()
        elif file_type in ['txt', 'md', 'markdown', 'text']:
            return TextParser()
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    @staticmethod
    def get_file_type(filename: str) -> str:
        """Get file type from filename"""
        extension = filename.lower().split('.')[-1]
        return extension
