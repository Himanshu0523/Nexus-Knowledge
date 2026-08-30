import contextvars
from typing import Optional

request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
trace_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("trace_id", default=None)
span_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("span_id", default=None)
tenant_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("tenant_id", default=None)
user_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_id", default=None)


def set_telemetry_context(
    request_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    if request_id is not None:
        request_id_ctx.set(request_id)
    if trace_id is not None:
        trace_id_ctx.set(trace_id)
    if span_id is not None:
        span_id_ctx.set(span_id)
    if tenant_id is not None:
        tenant_id_ctx.set(tenant_id)
    if user_id is not None:
        user_id_ctx.set(user_id)


def get_telemetry_context():
    return {
        "request_id": request_id_ctx.get(),
        "trace_id": trace_id_ctx.get(),
        "span_id": span_id_ctx.get(),
        "tenant_id": tenant_id_ctx.get(),
        "user_id": user_id_ctx.get(),
    }


def clear_telemetry_context():
    request_id_ctx.set(None)
    trace_id_ctx.set(None)
    span_id_ctx.set(None)
    tenant_id_ctx.set(None)
    user_id_ctx.set(None)
