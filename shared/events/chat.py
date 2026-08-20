from .base import EventEnvelope
from typing import Optional, Dict, Any

# ── Topic Names ───────────────────────────────────────────────
TOPIC_MESSAGE_CREATED     = "chat.message.created"
TOPIC_RESPONSE_COMPLETED  = "chat.response.completed"
TOPIC_RESPONSE_FAILED     = "chat.response.failed"
TOPIC_TOOL_EXECUTED       = "chat.tool.executed"
TOPIC_DOCUMENT_INGESTED   = "document.ingested"
TOPIC_DOCUMENT_DELETED    = "document.deleted"

ALL_TOPICS = [
    TOPIC_MESSAGE_CREATED,
    TOPIC_RESPONSE_COMPLETED,
    TOPIC_RESPONSE_FAILED,
    TOPIC_TOOL_EXECUTED,
    TOPIC_DOCUMENT_INGESTED,
    TOPIC_DOCUMENT_DELETED,
]

# ── Factory helpers ───────────────────────────────────────────

def message_created_event(
    conversation_id: str,
    message_id: str,
    user_message: str,
    tenant_id: str = "default",
    user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=TOPIC_MESSAGE_CREATED,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        data={
            "conversation_id": conversation_id,
            "message_id": message_id,
            "user_message": user_message,
            "user_id": user_id,
        },
    )


def response_completed_event(
    conversation_id: str,
    message_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    rag_used: bool = False,
    tenant_id: str = "default",
    correlation_id: Optional[str] = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=TOPIC_RESPONSE_COMPLETED,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        data={
            "conversation_id": conversation_id,
            "message_id": message_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "rag_used": rag_used,
        },
    )


def response_failed_event(
    conversation_id: str,
    error_code: str,
    error_message: str,
    tenant_id: str = "default",
    correlation_id: Optional[str] = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=TOPIC_RESPONSE_FAILED,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        data={
            "conversation_id": conversation_id,
            "error_code": error_code,
            "error_message": error_message,
        },
    )


def tool_executed_event(
    conversation_id: str,
    tool_name: str,
    success: bool,
    latency_ms: float,
    tenant_id: str = "default",
    correlation_id: Optional[str] = None,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=TOPIC_TOOL_EXECUTED,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        data={
            "conversation_id": conversation_id,
            "tool_name": tool_name,
            "success": success,
            "latency_ms": latency_ms,
        },
    )


def document_ingested_event(
    document_id: str,
    filename: str,
    chunks: int,
    tenant_id: str = "default",
) -> EventEnvelope:
    return EventEnvelope(
        event_type=TOPIC_DOCUMENT_INGESTED,
        tenant_id=tenant_id,
        data={
            "document_id": document_id,
            "filename": filename,
            "chunks": chunks,
        },
    )
