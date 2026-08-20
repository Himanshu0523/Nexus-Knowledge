import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Patterns for sensitive leakage (API Keys, Bearer Tokens, SSNs)
PII_PATTERNS = [
    (r"sk_[a-zA-Z0-9_]{20,}", "[REDACTED_API_KEY]"),
    (r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", "[REDACTED_TOKEN]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
]

class OutputGuard:
    """Sanitizer and safety checker for LLM generated output."""

    def __init__(self):
        self.rules = [(re.compile(pattern, re.IGNORECASE), replacement) for pattern, replacement in PII_PATTERNS]

    def sanitize(self, output: str) -> str:
        """Scan and redact any sensitive leaks in the LLM output."""
        if not output:
            return ""

        sanitized = output
        for regex, replacement in self.rules:
            if regex.search(sanitized):
                logger.warning(f"[OutputGuard] Redacted sensitive leak pattern: {regex.pattern}")
                sanitized = regex.sub(replacement, sanitized)

        return sanitized

output_guard = OutputGuard()
