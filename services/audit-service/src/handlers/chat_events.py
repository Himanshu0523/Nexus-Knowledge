import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger("audit.handlers")

# In-memory audit log (replace with DB write in production)
_audit_log: list = []


def _write_audit(event_type: str, event: dict):
    record = {
        "audit_id":       f"aud_{len(_audit_log):06d}",
        "event_id":       event.get("event_id"),
        "event_type":     event_type,
        "tenant_id":      event.get("tenant_id"),
        "timestamp":      event.get("timestamp"),
        "recorded_at":    datetime.now(timezone.utc).isoformat(),
        "data":           event.get("data", {}),
    }
    _audit_log.append(record)
    logger.info(f"[AUDIT] {event_type} | event_id={record['event_id']} | tenant={record['tenant_id']}")


def handle_message_created(event: dict):
    _write_audit("chat.message.created", event)


def handle_response_completed(event: dict):
    _write_audit("chat.response.completed", event)


def handle_response_failed(event: dict):
    _write_audit("chat.response.failed", event)
