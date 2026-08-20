from typing import Optional, Dict, Any, Generator, List
import httpx
import uuid
import json

from .models import ChatResponse, StreamEvent
from .errors import ChatbotError, AuthenticationError, InvalidRequestError, ConnectionError
from .streaming import StreamResponse

class ChatbotClient:
    """Canonical Python SDK Client for the Chatbot Platform"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:8000",
        timeout: float = 60.0,
        tenant_id: str = "default"
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.api_prefix = f"{self.base_url}/api/v1"
        self.timeout = timeout
        self.tenant_id = tenant_id
        
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Chatbot-Python-SDK/1.0.0"
        }
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def _handle_error_response(self, response: httpx.Response):
        """Parse error schema from platform"""
        try:
            data = response.json()
            err = data.get("error", {})
            code = err.get("code", "API_ERROR")
            msg = err.get("message", response.text)
            req_id = err.get("request_id")
        except Exception:
            code = "HTTP_ERROR"
            msg = response.text
            req_id = None
            
        if response.status_code in (401, 403):
            raise AuthenticationError(msg, request_id=req_id)
        elif response.status_code == 400:
            raise InvalidRequestError(msg, request_id=req_id)
        else:
            raise ChatbotError(msg, code=code, request_id=req_id, status_code=response.status_code)

    def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        knowledge_base_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """Send a synchronous message to the chatbot"""
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex[:10]}"
            
        meta = metadata or {}
        meta["tenant_id"] = self.tenant_id
        
        payload = {
            "conversation_id": conversation_id,
            "message": message,
            "knowledge_base_id": knowledge_base_id,
            "metadata": meta
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.api_prefix}/chat",
                    headers=self.headers,
                    json=payload
                )
                
                if resp.status_code != 200:
                    self._handle_error_response(resp)
                    
                data = resp.json()
                return ChatResponse(**data)
                
        except httpx.RequestError as e:
            raise ConnectionError(f"HTTP Connection failed: {str(e)}")

    def chat_stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        knowledge_base_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Generator[StreamEvent, None, None]:
        """Stream response tokens & events using SSE"""
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex[:10]}"
            
        meta = metadata or {}
        meta["tenant_id"] = self.tenant_id
        
        payload = {
            "conversation_id": conversation_id,
            "message": message,
            "knowledge_base_id": knowledge_base_id,
            "metadata": meta
        }
        
        try:
            client = httpx.Client(timeout=self.timeout)
            req = client.build_request(
                "POST",
                f"{self.api_prefix}/chat/stream",
                headers=self.headers,
                json=payload
            )
            resp = client.send(req, stream=True)
            
            if resp.status_code != 200:
                self._handle_error_response(resp)
                
            stream = StreamResponse(resp)
            for event in stream:
                yield event
            stream.close()
            client.close()
            
        except httpx.RequestError as e:
            raise ConnectionError(f"Streaming connection failed: {str(e)}")

    def upload_document(self, file_path: str) -> Dict[str, Any]:
        """Upload document for RAG ingestion"""
        document_id = f"doc_{uuid.uuid4().hex[:10]}"
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                data = {
                    "document_id": document_id,
                    "tenant_id": self.tenant_id
                }
                
                headers = {k: v for k, v in self.headers.items() if k.lower() != "content-type"}
                
                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(
                        f"{self.api_prefix}/documents",
                        headers=headers,
                        files=files,
                        data=data
                    )
                    if resp.status_code != 200:
                        self._handle_error_response(resp)
                    return resp.json()
        except Exception as e:
            raise ChatbotError(f"Document upload failed: {str(e)}")
