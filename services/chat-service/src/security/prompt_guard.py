import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

# Common prompt injection patterns
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above)\s+instructions",
    r"disregard\s+(all\s+)?system\s+prompts",
    r"system\s*:\s*you\s+are\s+now",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions|secret)",
    r"drop\s+table",
    r"exec(ute)?\s+sql",
    r"delete\s+from",
]

class PromptGuard:
    """Security inspector for user inputs and RAG contexts before LLM execution."""

    def __init__(self, blocked_patterns: List[str] = None):
        patterns = INJECTION_PATTERNS + (blocked_patterns or [])
        self.regex = re.compile("|".join(patterns), re.IGNORECASE)

    def inspect(self, prompt: str) -> Tuple[bool, str]:
        """
        Inspect input text for injection patterns.
        Returns (is_safe: bool, reason: str)
        """
        if not prompt or not isinstance(prompt, str):
            return True, "Valid"

        match = self.regex.search(prompt)
        if match:
            logger.warning(f"[PromptGuard] Injection pattern detected: '{match.group(0)}'")
            return False, f"Prompt injection pattern detected: '{match.group(0)}'"

        return True, "Safe"

    def sanitize(self, text: str) -> str:
        """Sanitize text by escaping potential control markers."""
        if not text:
            return ""
        # Remove null bytes and isolate system override commands
        cleaned = text.replace("\x00", "")
        return cleaned.strip()

prompt_guard = PromptGuard()
