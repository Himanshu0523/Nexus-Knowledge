import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
from shared.telemetry.context import set_telemetry_context, clear_telemetry_context
from shared.telemetry.metrics import metrics
from shared.telemetry.tracer import tracer
from shared.telemetry.logging import get_telemetry_logger

logger = get_telemetry_logger("telemetry.middleware")


class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    FastAPI / Starlette Middleware for automated end-to-end Telemetry:
    - Context propagation (request_id, trace_id, tenant_id)
    - Automated root span tracing
    - Automated Prometheus HTTP request & SSE metrics collection
    - Standard response headers injection (X-Request-ID, X-Trace-ID, X-Process-Time, traceparent)
    """

    def __init__(self, app, service_name: str = "microservice"):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip internal health checks from producing spammy root spans if desired, or trace all
        path = request.url.path
        method = request.method

        # 1. Context Extraction
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        tenant_id = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id") or "default"
        trace_id, parent_span_id = tracer.extract_headers(dict(request.headers))

        set_telemetry_context(
            request_id=request_id,
            trace_id=trace_id,
            tenant_id=tenant_id
        )

        request.state.request_id = request_id
        request.state.trace_id = trace_id
        request.state.tenant_id = tenant_id

        # 2. SSE Connection Tracking
        is_sse = "stream" in path
        if is_sse:
            metrics.sse_active_connections.inc(1, {"endpoint": path, "tenant_id": tenant_id})

        start_time = time.time()
        status_code = 500

        # 3. Span Execution & Next Call
        span_name = f"HTTP {method} {path}"
        try:
            with tracer.start_span(
                name=span_name,
                attributes={
                    "http.method": method,
                    "http.url": str(request.url),
                    "http.path": path,
                    "service": self.service_name,
                    "tenant_id": tenant_id,
                    "request_id": request_id,
                },
                parent_span_id=parent_span_id,
            ) as span:

                response = await call_next(request)
                status_code = response.status_code

                span.set_attribute("http.status_code", status_code)
                if status_code >= 400:
                    span.status = "ERROR"

                duration = time.time() - start_time

                # 4. Metrics Recording
                metrics.record_http_request(
                    method=method,
                    endpoint=path,
                    status=status_code,
                    duration=duration,
                    tenant_id=tenant_id,
                )

                # 5. Inject Telemetry Headers into Response
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Trace-ID"] = trace_id
                response.headers["X-Process-Time"] = f"{duration:.4f}"
                response.headers["traceparent"] = tracer.format_w3c_traceparent(trace_id, span.span_id)

                return response

        except Exception as exc:
            duration = time.time() - start_time
            metrics.record_http_request(
                method=method,
                endpoint=path,
                status=500,
                duration=duration,
                tenant_id=tenant_id,
            )
            logger.error(f"Request failed with unhandled exception: {exc}", exc_info=True)
            raise exc

        finally:
            if is_sse:
                metrics.sse_active_connections.dec(1, {"endpoint": path, "tenant_id": tenant_id})
            clear_telemetry_context()
