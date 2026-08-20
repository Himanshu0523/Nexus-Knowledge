from typing import Generator, Dict, Any
import json
import httpx
from .models import StreamEvent
from .errors import ChatbotError

class StreamResponse:
    """Synchronous & Generator wrapper over SSE response stream"""
    
    def __init__(self, response: httpx.Response):
        self._response = response
        
    def __iter__(self) -> Generator[StreamEvent, None, None]:
        for line in self._response.iter_lines():
            if line.startswith("data: "):
                raw_data = line[6:].strip()
                if not raw_data:
                    continue
                try:
                    payload = json.loads(raw_data)
                    yield StreamEvent(**payload)
                except Exception:
                    continue
    
    def close(self):
        self._response.close()
