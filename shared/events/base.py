from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import uuid

@dataclass
class EventEnvelope:
    """Standard event envelope for all Kafka events"""
    event_type: str
    data: Dict[str, Any]
    tenant_id: str = "default"
    producer: str = "chat-service"
    version: int = 1
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
