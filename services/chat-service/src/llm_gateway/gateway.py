import asyncio
import os
import time
import logging
from typing import AsyncGenerator, Dict, List, Any, Optional
from .models import (
    BackendType,
    BackendStatus,
    BackendConfig,
    TenantPolicy,
    LLMRequest,
    LLMResponse,
    StreamChunk
)
from .adapters.base import BaseLLMAdapter
from .adapters.vllm_adapter import VLLMAdapter
from .adapters.ollama_adapter import OllamaAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.mock_adapter import MockAdapter
from .circuit_breaker import CircuitBreaker
from .router import LLMRouter
from .policy import PolicyEngine

logger = logging.getLogger(__name__)

class LLMGateway:
    """
    Open-Source & Multi-Provider LLM Gateway.
    Decouples application code from underlying LLM providers (vLLM, Ollama, OpenAI, Mock).
    Provides automatic failover, circuit breaker health tracking, tenant policies, and telemetry.
    """

    def __init__(self):
        self.adapters: Dict[str, BaseLLMAdapter] = {}
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_cooldown=30.0)
        self.router = LLMRouter()
        self.policy_engine = PolicyEngine()
        
        # Telemetry & metrics tracking
        self.metrics: Dict[str, Dict[str, Any]] = {}

        # Auto-register default mock backend
        mock_cfg = BackendConfig(name="mock", type=BackendType.MOCK, base_url="", model_name="mock-model")
        self.register_backend(MockAdapter(mock_cfg))

    def register_backend(self, adapter: BaseLLMAdapter):
        """Register a backend adapter instance."""
        self.adapters[adapter.name] = adapter
        self.metrics[adapter.name] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_latency_ms": 0.0,
        }
        logger.info(f"Registered LLM backend adapter: '{adapter.name}' (type={adapter.backend_type})")

    def unregister_backend(self, name: str):
        """Remove a backend adapter."""
        if name in self.adapters:
            del self.adapters[name]
            del self.metrics[name]

    def register_tenant_policy(self, policy: TenantPolicy):
        """Register tenant policy in PolicyEngine."""
        self.policy_engine.register_tenant_policy(policy)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate non-streaming response with automatic fallback across healthy backends.
        """
        # 1. Apply policy constraints
        processed_req = self.policy_engine.apply_policy(request)
        tenant_policy = self.policy_engine.get_tenant_policy(processed_req.tenant_id)

        # 2. Get candidate backends from router
        candidates = self.router.resolve_candidate_backends(
            request=processed_req,
            adapters=self.adapters,
            circuit_breaker=self.circuit_breaker,
            policy=tenant_policy
        )

        if not candidates:
            raise RuntimeError("No LLM backend adapters registered in gateway.")

        attempt_history: List[Dict[str, Any]] = []

        # 3. Iterate over candidates with fallback
        for idx, adapter in enumerate(candidates):
            backend_name = adapter.name
            start_t = time.time()
            try:
                logger.info(
                    f"LLM Gateway attempting request {processed_req.request_id} using backend '{backend_name}' "
                    f"(attempt {idx + 1}/{len(candidates)})"
                )
                self.metrics[backend_name]["total_requests"] += 1

                # Execute call
                response = await adapter.generate(processed_req)
                
                # Record success
                self.circuit_breaker.record_success(backend_name)
                lat_ms = (time.time() - start_t) * 1000.0
                
                # Record metrics
                m = self.metrics[backend_name]
                m["successful_requests"] += 1
                m["total_prompt_tokens"] += response.prompt_tokens
                m["total_completion_tokens"] += response.completion_tokens
                m["total_latency_ms"] += lat_ms

                response.fallback_occurred = (idx > 0)
                attempt_history.append({
                    "backend": backend_name,
                    "status": "success",
                    "latency_ms": lat_ms
                })
                response.attempt_history = attempt_history
                return response

            except Exception as e:
                lat_ms = (time.time() - start_t) * 1000.0
                logger.warning(f"Backend '{backend_name}' failed during generation: {e}")
                self.circuit_breaker.record_failure(backend_name, e)
                
                if backend_name in self.metrics:
                    self.metrics[backend_name]["failed_requests"] += 1

                attempt_history.append({
                    "backend": backend_name,
                    "status": "error",
                    "error": str(e),
                    "latency_ms": lat_ms
                })

        # 4. Final fallback to mock if available
        mock_adapter = next((a for a in self.adapters.values() if a.backend_type == "mock"), None)
        if mock_adapter:
            logger.warning("All primary LLM backends failed! Invoking emergency MockAdapter fallback.")
            res = await mock_adapter.generate(processed_req)
            res.fallback_occurred = True
            res.attempt_history = attempt_history
            return res

        raise RuntimeError(f"All candidate LLM backends failed: {attempt_history}")

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream response tokens with failover on initial connection failure.
        """
        processed_req = self.policy_engine.apply_policy(request)
        tenant_policy = self.policy_engine.get_tenant_policy(processed_req.tenant_id)

        candidates = self.router.resolve_candidate_backends(
            request=processed_req,
            adapters=self.adapters,
            circuit_breaker=self.circuit_breaker,
            policy=tenant_policy
        )

        for idx, adapter in enumerate(candidates):
            backend_name = adapter.name
            tokens_yielded = 0
            try:
                logger.info(f"LLM Gateway streaming via backend '{backend_name}'")
                async for chunk in adapter.stream(processed_req):
                    tokens_yielded += 1
                    yield chunk

                self.circuit_breaker.record_success(backend_name)
                return

            except Exception as e:
                logger.warning(f"Backend '{backend_name}' stream error after {tokens_yielded} tokens: {e}")
                self.circuit_breaker.record_failure(backend_name, e)

                # If tokens were already sent to client, we cannot failover smoothlymid-stream
                if tokens_yielded > 0:
                    yield StreamChunk(
                        delta=f"\n[Stream interrupted due to backend error: {e}]",
                        is_final=True,
                        backend_used=backend_name
                    )
                    return

        # Fallback stream if connection failed before yielding tokens
        mock_adapter = next((a for a in self.adapters.values() if a.backend_type == "mock"), None)
        if mock_adapter:
            async for chunk in mock_adapter.stream(processed_req):
                yield chunk

    def get_health_status(self) -> Dict[str, Any]:
        """Return health status & circuit breaker state for all registered backends."""
        status = {}
        for name, adapter in self.adapters.items():
            circuit_state = self.circuit_breaker.get_state(name)
            metrics = self.metrics.get(name, {})
            status[name] = {
                "type": adapter.backend_type,
                "circuit_state": circuit_state,
                "metrics": metrics
            }
        return status

def create_gateway_from_env() -> LLMGateway:
    """
    Factory function to initialize LLMGateway using environment variables.
    Supports LLM_PROVIDER (vllm, ollama, openai, mock), LLM_MODEL, LLM_BASE_URL, LLM_API_KEY.
    """
    gateway = LLMGateway()

    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    model = os.getenv("LLM_MODEL", "default")
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    api_key = os.getenv("LLM_API_KEY", "")

    # Always register primary env backend if not mock
    if provider == "vllm":
        cfg = BackendConfig(name="vllm_primary", type=BackendType.VLLM, base_url=base_url, api_key=api_key, model_name=model)
        gateway.register_backend(VLLMAdapter(cfg))
        gateway.router.set_default_priority(["vllm_primary", "mock"])

    elif provider == "ollama":
        cfg = BackendConfig(name="ollama_primary", type=BackendType.OLLAMA, base_url=base_url, model_name=model)
        gateway.register_backend(OllamaAdapter(cfg))
        gateway.router.set_default_priority(["ollama_primary", "mock"])

    elif provider == "openai":
        cfg = BackendConfig(name="openai_primary", type=BackendType.OPENAI, base_url=base_url, api_key=api_key, model_name=model)
        gateway.register_backend(OpenAIAdapter(cfg))
        gateway.router.set_default_priority(["openai_primary", "mock"])

    else:
        gateway.router.set_default_priority(["mock"])

    return gateway

# Global singleton instance for chat-service
llm_gateway = create_gateway_from_env()
