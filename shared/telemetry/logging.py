import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from shared.telemetry.context import get_telemetry_context


class JSONTelemetryFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings with contextual telemetry data (trace_id, span_id, request_id, tenant_id).
    """

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        telemetry_ctx = get_telemetry_context()

        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": telemetry_ctx.get("request_id"),
            "trace_id": telemetry_ctx.get("trace_id"),
            "span_id": telemetry_ctx.get("span_id"),
            "tenant_id": telemetry_ctx.get("tenant_id"),
        }

        if telemetry_ctx.get("user_id"):
            log_obj["user_id"] = telemetry_ctx.get("user_id")

        # Include extra fields passed in record.__dict__
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process"
        }

        extra_attributes = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extra_attributes:
            log_obj["extra"] = extra_attributes

        # Exception formatting
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


def setup_telemetry_logging(service_name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Configures the root logger to output JSON telemetry logs to stdout.
    """
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(JSONTelemetryFormatter(service_name=service_name))

    root_logger.addHandler(console_handler)

    logger = logging.getLogger(service_name)
    logger.info(f"Initialized Telemetry Structured JSON Logging for service: {service_name}")
    return logger


def get_telemetry_logger(name: str) -> logging.Logger:
    """Retrieve named logger."""
    return logging.getLogger(name)
