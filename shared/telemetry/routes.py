from fastapi import APIRouter, Query, Response, FastAPI
from typing import Optional
from shared.telemetry.metrics import metrics
from shared.telemetry.tracer import tracer

router = APIRouter(tags=["Telemetry"])

@router.get("/metrics", response_class=Response)
async def get_metrics():
    """
    Exposes Prometheus text format metrics endpoint for scraping.
    """
    body = metrics.generate_prometheus_text()
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )

@router.get("/traces")
async def get_traces(trace_id: Optional[str] = Query(None, description="Optional W3C Trace ID to filter trace spans")):
    """
    Exposes recent in-memory trace spans or specific trace details.
    """
    if trace_id:
        spans = tracer.exporter.get_trace(trace_id)
        return {"trace_id": trace_id, "spans": spans, "count": len(spans)}
    
    recent_spans = tracer.exporter.get_recent_spans(limit=50)
    return {"spans": recent_spans, "count": len(recent_spans)}


def register_telemetry_routes(app: FastAPI, prefix: str = ""):
    """
    Utility function to mount telemetry routes (/metrics, /traces) on a FastAPI application.
    """
    app.include_router(router, prefix=prefix)
