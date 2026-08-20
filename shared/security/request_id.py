import uuid
from typing import Optional

def generate_request_id() -> str:
    """Generate a unique request tracing ID."""
    return f"req_{uuid.uuid4().hex[:12]}"
