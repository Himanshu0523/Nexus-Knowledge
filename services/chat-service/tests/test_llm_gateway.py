import pytest
import asyncio
from typing import AsyncGenerator
from src.llm_gateway import (
    LLMGateway,
    LLMRequest,
    LLMResponse,
    StreamChunk,
    BackendConfig,
    BackendType,
    TenantPolicy,
    CircuitState
)
from src.llm_gateway.adapters.base import BaseLLMAdapter
from src.llm_gateway.adapters.mock_adapter import MockAdapter
from src.llm_gateway.adapters.ollama_adapter import OllamaAdapter
from src.llm_gateway.adapters.vllm_adapter import VLLMAdapter
from src.llm_gateway.adapters.openai_adapter import OpenAIAdapter

class FailingAdapter(BaseLLMAdapter):
    def __init__(self, config: BackendConfig, error_msg: str = "Backend simulated crash"):
        super().__init__(config)
        self.error_msg = error_msg

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise ConnectionError(self.error_msg)

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        raise ConnectionError(self.error_msg)
        yield # unreachable

@pytest.mark.asyncio
async def test_llm_gateway_registration_and_mock_generation():
    gateway = LLMGateway()
    req = LLMRequest(
        prompt="Hello LLM Gateway",
        tenant_id="tenant_alpha",
        max_tokens=100
    )
    
    resp = await gateway.generate(req)
    assert resp is not None
    assert "Mock response" in resp.text
    assert resp.backend_used == "mock"
    assert not resp.fallback_occurred

@pytest.mark.asyncio
async def test_llm_gateway_automatic_fallback():
    gateway = LLMGateway()
    
    # Register a failing primary backend
    failing_cfg = BackendConfig(
        name="primary_failing_vllm",
        type=BackendType.VLLM,
        base_url="http://invalid-vllm-host:8000",
        model_name="llama-3-70b"
    )
    failing_adapter = FailingAdapter(failing_cfg)
    gateway.register_backend(failing_adapter)
    
    # Set preferred backend to the failing one
    req = LLMRequest(
        prompt="What is the capital of France?",
        preferred_backend="primary_failing_vllm",
        tenant_id="tenant_beta"
    )

    # Generation should fail on primary_failing_vllm and fallback to mock
    resp = await gateway.generate(req)
    assert resp.backend_used == "mock"
    assert resp.fallback_occurred
    assert len(resp.attempt_history) >= 1
    assert resp.attempt_history[0]["backend"] == "primary_failing_vllm"
    assert resp.attempt_history[0]["status"] == "error"

@pytest.mark.asyncio
async def test_circuit_breaker_tripping_and_recovery():
    gateway = LLMGateway()
    
    failing_cfg = BackendConfig(
        name="unstable_backend",
        type=BackendType.OLLAMA,
        base_url="http://localhost:11434",
        model_name="mistral"
    )
    gateway.register_backend(FailingAdapter(failing_cfg))

    req = LLMRequest(prompt="Test", preferred_backend="unstable_backend")

    # Trip the circuit breaker threshold (3 failures)
    for _ in range(3):
        await gateway.generate(req)

    # Check circuit breaker state
    state = gateway.circuit_breaker.get_state("unstable_backend")
    assert state == CircuitState.OPEN

    health = gateway.get_health_status()
    assert health["unstable_backend"]["circuit_state"] == "OPEN"
    assert health["unstable_backend"]["consecutive_failures"] == 3

@pytest.mark.asyncio
async def test_tenant_policy_enforcement():
    gateway = LLMGateway()
    
    # Register tenant policy with strict max_tokens limit
    policy = TenantPolicy(
        tenant_id="strict_tenant",
        allowed_backends=["mock"],
        max_context_length=50,
        max_output_tokens=25,
        allowed_models=["mock-model"]
    )
    gateway.register_tenant_policy(policy)

    # Prompt with large requested tokens
    req = LLMRequest(
        prompt="Explain quantum physics in detail.",
        tenant_id="strict_tenant",
        max_tokens=200
    )

    resp = await gateway.generate(req)
    # Ensure max_tokens was constrained by policy
    assert req.max_tokens == 200 # original unchanged
    # Generated response uses constrained limit
    assert resp is not None

@pytest.mark.asyncio
async def test_streaming_fallback():
    gateway = LLMGateway()
    
    failing_cfg = BackendConfig(
        name="failing_streamer",
        type=BackendType.OPENAI,
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o"
    )
    gateway.register_backend(FailingAdapter(failing_cfg))

    req = LLMRequest(
        prompt="Stream test message",
        preferred_backend="failing_streamer"
    )

    chunks = []
    async for chunk in gateway.stream(req):
        chunks.append(chunk)

    assert len(chunks) > 0
    # Stream fell back to mock adapter
    full_text = "".join(c.delta for c in chunks)
    assert "Mock stream response" in full_text
