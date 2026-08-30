"""
LLM Gateway Package for Nexus AI Chat Service.
Provides unified routing, multi-backend adapters (vLLM, Ollama, OpenAI, Mock),
automatic fallback, circuit breaker health monitoring, and tenant policy enforcement.
"""

from .models import (
    BackendType,
    BackendStatus,
    BackendConfig,
    TenantPolicy,
    LLMRequest,
    LLMResponse,
    StreamChunk
)
from .circuit_breaker import CircuitBreaker, CircuitState
from .policy import PolicyEngine
from .router import LLMRouter
from .gateway import LLMGateway, llm_gateway

__all__ = [
    "BackendType",
    "BackendStatus",
    "BackendConfig",
    "TenantPolicy",
    "LLMRequest",
    "LLMResponse",
    "StreamChunk",
    "CircuitBreaker",
    "CircuitState",
    "PolicyEngine",
    "LLMRouter",
    "LLMGateway",
    "llm_gateway",
]
