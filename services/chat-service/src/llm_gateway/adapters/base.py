from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional
from ..models import BackendConfig, LLMRequest, LLMResponse, StreamChunk

class BaseLLMAdapter(ABC):
    """Abstract base class for all LLM backend adapters."""

    def __init__(self, config: BackendConfig):
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def backend_type(self) -> str:
        return self.config.type.value

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate complete non-streaming response."""
        pass

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        """Stream response tokens chunk by chunk."""
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """Check if backend is healthy and responding."""
        pass
