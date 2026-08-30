import re
import logging
from typing import Tuple, List, Dict, Any
from .models import PIIPolicy, PIIAction, PIIType

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for standard PII types
PII_PATTERNS: Dict[PIIType, re.Pattern] = {
    PIIType.EMAIL: re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', re.IGNORECASE),
    PIIType.PHONE: re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
    PIIType.SSN: re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    PIIType.CREDIT_CARD: re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
    PIIType.API_KEY: re.compile(r'\b(?:sk-[a-zA-Z0-9]{20,T}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}|bearer\s+[a-zA-Z0-9\-._~+/]+=*)\b', re.IGNORECASE),
    PIIType.IP_ADDRESS: re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
}

PII_PLACEHOLDERS: Dict[PIIType, str] = {
    PIIType.EMAIL: "[REDACTED_EMAIL]",
    PIIType.PHONE: "[REDACTED_PHONE]",
    PIIType.SSN: "[REDACTED_SSN]",
    PIIType.CREDIT_CARD: "[REDACTED_CARD]",
    PIIType.API_KEY: "[REDACTED_SECRET]",
    PIIType.IP_ADDRESS: "[REDACTED_IP]",
    PIIType.CUSTOM: "[REDACTED_CUSTOM]",
}


class PIISanitizer:
    """
    Engine for inspecting, scrubbing, or blocking prompts based on tenant PII policies.
    """

    def inspect_and_sanitize(self, text: str, policy: PIIPolicy) -> Tuple[str, bool, List[str]]:
        """
        Processes text according to the tenant's PIIPolicy.
        Returns:
            sanitized_text: Modified text if SCRUB, or original text if LOG_ONLY / no match.
            pii_detected: True if any PII pattern was found.
            detected_types: List of PII types identified.
        """
        if not policy.enabled or not text:
            return text, False, []

        detected_types: List[str] = []
        sanitized_text = text
        pii_detected = False

        # 1. Standard PII Types
        for pii_type in policy.pii_types:
            pattern = PII_PATTERNS.get(pii_type)
            if not pattern:
                continue

            matches = pattern.findall(sanitized_text)
            if matches:
                pii_detected = True
                detected_types.append(pii_type.value)
                logger.info(f"[PIISanitizer] Detected {pii_type.value} in text (count={len(matches)})")

                if policy.action == PIIAction.SCRUB:
                    placeholder = PII_PLACEHOLDERS.get(pii_type, "[REDACTED]")
                    sanitized_text = pattern.sub(placeholder, sanitized_text)

        # 2. Custom Regexes
        for idx, custom_regex in enumerate(policy.custom_regexes):
            try:
                c_pattern = re.compile(custom_regex, re.IGNORECASE)
                matches = c_pattern.findall(sanitized_text)
                if matches:
                    pii_detected = True
                    detected_types.append(f"custom_pattern_{idx+1}")
                    logger.info(f"[PIISanitizer] Detected custom PII pattern #{idx+1} in text")
                    if policy.action == PIIAction.SCRUB:
                        sanitized_text = c_pattern.sub("[REDACTED_CUSTOM]", sanitized_text)
            except re.error as e:
                logger.error(f"[PIISanitizer] Invalid custom regex '{custom_regex}': {e}")

        return sanitized_text, pii_detected, list(set(detected_types))
