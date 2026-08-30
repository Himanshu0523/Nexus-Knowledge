"""
Shared Telemetry & Observability Subsystem
Provides metrics (Prometheus), distributed tracing (OpenTelemetry compatible W3C trace context),
and structured JSON logging with trace/request context correlation across microservices.
"""

from shared.telemetry.metrics import metrics
from shared.telemetry.tracer import tracer, Span
from shared.telemetry.logging import setup_telemetry_logging, get_telemetry_logger
from shared.telemetry.middleware import TelemetryMiddleware
from shared.telemetry.routes import router as telemetry_router, register_telemetry_routes

__all__ = [
    "metrics",
    "tracer",
    "Span",
    "setup_telemetry_logging",
    "get_telemetry_logger",
    "TelemetryMiddleware",
    "telemetry_router",
    "register_telemetry_routes",
]

