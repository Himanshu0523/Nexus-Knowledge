import time
import uuid
import secrets
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
from shared.telemetry.context import (
    trace_id_ctx,
    span_id_ctx,
    request_id_ctx,
    tenant_id_ctx,
)


@dataclass
class Event:
    name: str
    timestamp: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "OK"  # "OK" or "ERROR"
    error_message: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Event] = field(default_factory=list)

    def finish(self, status: str = "OK", error_message: Optional[str] = None):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 3)
        self.status = status
        if error_message:
            self.error_message = error_message

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        self.events.append(Event(name=name, attributes=attributes or {}))

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["events"] = [asdict(e) for e in self.events]
        return d


class TraceExporter:
    """In-memory trace buffer storing completed spans for query/export."""
    def __init__(self, max_spans: int = 1000):
        self.max_spans = max_spans
        self.spans: List[Span] = []
        self._trace_map: Dict[str, List[Span]] = {}

    def export(self, span: Span):
        self.spans.append(span)
        if span.trace_id not in self._trace_map:
            self._trace_map[span.trace_id] = []
        self._trace_map[span.trace_id].append(span)

        if len(self.spans) > self.max_spans:
            oldest = self.spans.pop(0)
            if oldest.trace_id in self._trace_map:
                self._trace_map[oldest.trace_id] = [
                    s for s in self._trace_map[oldest.trace_id] if s.span_id != oldest.span_id
                ]
                if not self._trace_map[oldest.trace_id]:
                    del self._trace_map[oldest.trace_id]

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._trace_map.get(trace_id, [])]

    def get_recent_spans(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in reversed(self.spans[-limit:])]


class Tracer:
    """Distributed Tracer using W3C Trace Context standards."""
    def __init__(self):
        self.exporter = TraceExporter()

    @staticmethod
    def generate_trace_id() -> str:
        """128-bit hex trace ID (32 hex characters)."""
        return secrets.token_hex(16)

    @staticmethod
    def generate_span_id() -> str:
        """64-bit hex span ID (16 hex characters)."""
        return secrets.token_hex(8)

    def extract_w3c_traceparent(self, traceparent: str) -> Optional[Tuple[str, str]]:
        """Parse W3C traceparent header: 00-{trace_id}-{span_id}-{trace_flags}"""
        try:
            parts = traceparent.strip().split("-")
            if len(parts) >= 4 and parts[0] == "00":
                trace_id = parts[1]
                span_id = parts[2]
                if len(trace_id) == 32 and len(span_id) == 16:
                    return trace_id, span_id
        except Exception:
            pass
        return None

    def format_w3c_traceparent(self, trace_id: str, span_id: str, sampled: bool = True) -> str:
        """Format W3C traceparent header string."""
        flags = "01" if sampled else "00"
        return f"00-{trace_id}-{span_id}-{flags}"

    def inject_headers(self, headers: Dict[str, str], trace_id: Optional[str] = None, span_id: Optional[str] = None) -> Dict[str, str]:
        """Inject trace context into headers for HTTP/RPC propagation."""
        t_id = trace_id or trace_id_ctx.get() or self.generate_trace_id()
        s_id = span_id or span_id_ctx.get() or self.generate_span_id()
        
        headers["traceparent"] = self.format_w3c_traceparent(t_id, s_id)
        headers["X-Trace-ID"] = t_id
        headers["X-Span-ID"] = s_id
        
        req_id = request_id_ctx.get()
        if req_id:
            headers["X-Request-ID"] = req_id
            
        tenant_id = tenant_id_ctx.get()
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id

        return headers

    def extract_headers(self, headers: Dict[str, str]) -> Tuple[str, Optional[str]]:
        """Extract trace_id and parent_span_id from incoming request headers."""
        # 1. W3C Header
        traceparent = headers.get("traceparent") or headers.get("Traceparent")
        if traceparent:
            extracted = self.extract_w3c_traceparent(traceparent)
            if extracted:
                return extracted[0], extracted[1]

        # 2. X-Trace-ID fallback
        t_id = headers.get("X-Trace-ID") or headers.get("x-trace-id")
        p_id = headers.get("X-Span-ID") or headers.get("x-span-id")
        
        if not t_id:
            t_id = self.generate_trace_id()

        return t_id, p_id

    @contextmanager
    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None, parent_span_id: Optional[str] = None):
        """Context manager to start and automatically finish a trace span."""
        current_trace_id = trace_id_ctx.get()
        if not current_trace_id:
            current_trace_id = self.generate_trace_id()
            trace_id_ctx.set(current_trace_id)

        active_span_id = span_id_ctx.get()
        parent_id = parent_span_id or active_span_id

        new_span_id = self.generate_span_id()
        token = span_id_ctx.set(new_span_id)

        span = Span(
            name=name,
            trace_id=current_trace_id,
            span_id=new_span_id,
            parent_span_id=parent_id,
            attributes=attributes or {}
        )

        tenant = tenant_id_ctx.get()
        if tenant and "tenant_id" not in span.attributes:
            span.set_attribute("tenant_id", tenant)

        req_id = request_id_ctx.get()
        if req_id and "request_id" not in span.attributes:
            span.set_attribute("request_id", req_id)

        try:
            yield span
            span.finish(status="OK")
        except Exception as e:
            span.finish(status="ERROR", error_message=str(e))
            span.set_attribute("exception.type", type(e).__name__)
            span.set_attribute("exception.message", str(e))
            raise
        finally:
            span_id_ctx.reset(token)
            self.exporter.export(span)


tracer = Tracer()
