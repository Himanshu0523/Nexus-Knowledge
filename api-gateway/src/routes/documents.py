from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from typing import List
import uuid
import httpx
import os

router = APIRouter()

CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://localhost:8001")

@router.get("/documents")
async def get_documents(request: Request, tenant_id: str = "default"):
    """List documents for a specific tenant"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CHAT_SERVICE_URL}/api/v1/documents",
                params={"tenant_id": tenant_id},
                timeout=10.0
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json()
            )
    except httpx.ConnectTimeout:
        raise HTTPException(
            status_code=504,
            detail={
                "error": {
                    "code": "TIMEOUT",
                    "message": "Connection to Chat Service timed out"
                }
            }
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": f"Service unavailable: {str(e)}"
                }
            }
        )



@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = "default"
):
    """Upload a document for RAG processing"""
    try:
        # Read file
        file_bytes = await file.read()
        
        # Generate document ID
        document_id = f"doc_{uuid.uuid4().hex[:10]}"
        
        # Send to chat service for processing
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CHAT_SERVICE_URL}/api/v1/documents/process",
                files={
                    "file": (file.filename, file_bytes, file.content_type)
                },
                data={
                    "document_id": document_id,
                    "tenant_id": tenant_id
                },
                timeout=300.0
            )
        
        if response.status_code == 200:
            return {
                "document_id": document_id,
                "status": "processing",
                "message": "Document uploaded and processing started"
            }
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json()
            )
            
    except httpx.ConnectTimeout:
        raise HTTPException(
            status_code=504,
            detail={
                "error": {
                    "code": "TIMEOUT",
                    "message": "Connection to Chat Service timed out"
                }
            }
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": f"Service unavailable: {str(e)}"
                }
            }
        )

@router.get("/documents/{document_id}")
async def get_document_status(document_id: str):
    """Get document processing status"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{CHAT_SERVICE_URL}/api/v1/documents/{document_id}/status"
        )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.json()
        )

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, tenant_id: str = "default"):
    """Delete a document from the knowledge base"""
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{CHAT_SERVICE_URL}/api/v1/documents/{document_id}",
            params={"tenant_id": tenant_id}
        )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.json()
        )
