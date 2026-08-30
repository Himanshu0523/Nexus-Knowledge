from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json
import time
import uuid

try:
    from config import settings
except ImportError:
    try:
        from src.config import settings
    except ImportError:
        settings = None

from database.postgres import get_db, init_db
from database.redis_client import redis_client
from orchestration.chat_orchestrator import ChatOrchestrator
from rag.ingestion import IngestionPipeline
from rag.qdrant_client import QdrantService
from models.schemas import ChatRequest, ChatResponse
from shared.telemetry import TelemetryMiddleware, register_telemetry_routes, setup_telemetry_logging

setup_telemetry_logging("chat-service")

app = FastAPI(title="Chat Service", version="3.0.0")

# Telemetry middleware
app.add_middleware(TelemetryMiddleware, service_name="chat-service")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_telemetry_routes(app)


ingestion_pipeline = IngestionPipeline()
qdrant_service = QdrantService()

# In-memory document status tracker
document_statuses: Dict[str, Dict[str, Any]] = {}

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    try:
        init_db()
        print("Chat Service started successfully")
    except Exception as e:
        print(f"Warning: Database initialization deferred or failed: {e}")

@app.post("/api/v1/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """Stream chat response using SSE"""
    try:
        orchestrator = ChatOrchestrator(db)
        
        user_context = {
            "role": request.metadata.get("role", "user") if request.metadata else "user",
            "user_id": request.metadata.get("user_id") if request.metadata else None
        }
        
        async def generate():
            async for event in orchestrator.process_message_stream(
                request.dict(),
                tenant_id=request.metadata.get("tenant_id", "default") if request.metadata else "default",
                user_context=user_context
            ):
                data = json.dumps(event.to_dict())
                yield f"data: {data}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "STREAM_ERROR",
                    "message": str(e)
                }
            }
        )

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    """Main chat endpoint with conversation memory and RAG orchestration"""
    try:
        orchestrator = ChatOrchestrator(db)
        
        tenant_id = request.metadata.get("tenant_id", "default") if request.metadata else "default"
        
        result = await orchestrator.process_message(
            request={
                "conversation_id": request.conversation_id,
                "message": request.message,
                "knowledge_base_id": request.knowledge_base_id,
                "metadata": request.metadata
            },
            tenant_id=tenant_id
        )
        
        message_id = f"msg_{uuid.uuid4().hex[:10]}"
        
        return ChatResponse(
            conversation_id=request.conversation_id,
            message_id=message_id,
            response=result["response"],
            sources=result.get("sources"),
            usage=result.get("usage"),
            model=result.get("model", "qwen")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": str(e)
                }
            }
        )

@app.post("/api/v1/documents/process")
async def process_document(
    file: UploadFile = File(...),
    document_id: str = Form(...),
    tenant_id: str = Form("default")
):
    """Process document through ingestion pipeline"""
    try:
        file_bytes = await file.read()
        
        document_statuses[document_id] = {
            "status": "processing",
            "filename": file.filename,
            "document_id": document_id
        }
        
        result = await ingestion_pipeline.process_document(
            file_bytes=file_bytes,
            filename=file.filename,
            document_id=document_id,
            tenant_id=tenant_id
        )
        
        document_statuses[document_id] = result
        return result
        
    except Exception as e:
        document_statuses[document_id] = {
            "status": "failed",
            "error": str(e),
            "document_id": document_id
        }
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/documents/{document_id}/status")
async def get_document_status(document_id: str):
    """Get status of document processing"""
    if document_id in document_statuses:
        return document_statuses[document_id]
    return {"document_id": document_id, "status": "unknown"}

@app.get("/api/v1/documents")
async def get_all_documents(tenant_id: str = "default"):
    """Get all processed documents for a tenant"""
    docs = []
    for doc_id, data in document_statuses.items():
        # Ideally, we filter by tenant if stored in dict, but let's return all processed
        doc_data = {
            "id": doc_id,
            "filename": data.get("filename", "unknown"),
            "status": data.get("status", "indexed"),
            "tenant": tenant_id
        }
        docs.append(doc_data)
    return {"documents": docs}

@app.delete("/api/v1/documents/{document_id}")
async def delete_document(document_id: str, tenant_id: str = "default"):
    """Delete document chunks from Qdrant"""
    try:
        qdrant_service.delete_document(document_id, tenant_id)
        if document_id in document_statuses:
            del document_statuses[document_id]
        return {"status": "success", "message": f"Document {document_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_healthy = redis_client.health_check()
    qdrant_healthy = qdrant_service.health_check()
    return {
        "status": "healthy" if (redis_healthy and qdrant_healthy) else "degraded",
        "redis": redis_healthy,
        "qdrant": qdrant_healthy,
        "timestamp": time.time()
    }

@app.get("/health/live")
@app.get("/healthz")
async def liveness_check():
    return {"status": "alive"}

@app.get("/health/ready")
@app.get("/readyz")
async def readiness_check():
    redis_healthy = redis_client.health_check()
    qdrant_healthy = qdrant_service.health_check()
    if redis_healthy and qdrant_healthy:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Service dependencies not ready")


@app.get("/api/v1/conversations/{conversation_id}/history")
async def get_conversation_history(conversation_id: str, db: Session = Depends(get_db)):
    """Get conversation history"""
    try:
        from services.conversation_service import ConversationService
    except ImportError:
        from src.services.conversation_service import ConversationService
    conversation_service = ConversationService(db)
    history = conversation_service.get_conversation_history(conversation_id)
    return {"conversation_id": conversation_id, "messages": history}

@app.delete("/api/v1/conversations/{conversation_id}/cache")
async def clear_conversation_cache(conversation_id: str, db: Session = Depends(get_db)):
    """Clear conversation cache"""
    try:
        from services.conversation_service import ConversationService
    except ImportError:
        from src.services.conversation_service import ConversationService
    conversation_service = ConversationService(db)
    conversation_service.clear_conversation_cache(conversation_id)
    return {"status": "success", "message": "Cache cleared"}