"""
PII Scrubbing Middleware and Pre-Processor for Nexus Knowledge.
Scans incoming raw text and masks sensitive enterprise data (emails, phones, API keys,
bearer tokens, SSNs, credit cards) before text chunking, embedding generation, or vector storage.
"""

import re
import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# Enterprise PII regex patterns and standard redaction tags
PII_RULES = [
    # API Keys (OpenAI, GitHub, Stripe, generic secrets)
    (re.compile(r"\b(?:sk|ghp|pk|api|key)_[a-zA-Z0-9_\-]{16,}\b", re.IGNORECASE), "[REDACTED_API_KEY]"),
    # Bearer tokens
    (re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE), "[REDACTED_TOKEN]"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b"), "[REDACTED_EMAIL]"),
    # Phone numbers (US & international formats)
    (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED_PHONE]"),
    # Social Security Numbers (SSN)
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    # Credit Card Numbers (16-digit spaced or dashed)
    (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"), "[REDACTED_CREDIT_CARD]"),
]


class PIIScrubber:
    """Enterprise PII detection and redaction engine."""

    def __init__(self, rules=None):
        self.rules = rules or PII_RULES

    def scrub(self, text: str) -> Tuple[str, Dict[str, int]]:
        """
        Scrub sensitive PII from text.
        Returns:
            (sanitized_text, redaction_counts)
        """
        if not text:
            return "", {}

        sanitized = text
        redaction_counts: Dict[str, int] = {}

        for pattern, replacement in self.rules:
            matches = pattern.findall(sanitized)
            if matches:
                tag = replacement
                redaction_counts[tag] = redaction_counts.get(tag, 0) + len(matches)
                sanitized = pattern.sub(replacement, sanitized)
                logger.info(f"[PIIScrubber] Redacted {len(matches)} instance(s) matching {tag}")

        return sanitized, redaction_counts

    def is_clean(self, text: str) -> bool:
        """Check if text contains any unmasked PII."""
        for pattern, _ in self.rules:
            if pattern.search(text):
                return False
        return True


# Global singleton instance
pii_scrubber = PIIScrubber()
