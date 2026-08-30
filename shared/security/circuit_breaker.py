import time
import asyncio
import logging
from enum import Enum
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"        # Normal operation, calls pass through
    OPEN = "OPEN"            # Circuit tripped, calls fail fast or execute fallback
    HALF_OPEN = "HALF_OPEN"  # Testing recovery, trial calls allowed


class CircuitBreakerOpenException(Exception):
    def __init__(self, service_name: str):
        super().__init__(f"Circuit breaker for service '{service_name}' is OPEN.")
        self.service_name = service_name


class CircuitBreaker:
    """
    Async Circuit Breaker implementation with state transitions,
    failure thresholding, and trial recovery.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 15.0,
        half_open_success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = time.time()
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, fallback: Optional[Callable] = None, **kwargs) -> Any:
        """Execute async or sync function wrapped in circuit breaker protection."""
        async with self._lock:
            now = time.time()
            if self.state == CircuitState.OPEN:
                if now - self.last_state_change >= self.recovery_timeout:
                    logger.info(f"CircuitBreaker[{self.name}] transitioning OPEN -> HALF_OPEN (Testing recovery)")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    if fallback:
                        if asyncio.iscoroutinefunction(fallback):
                            return await fallback(*args, **kwargs)
                        return fallback(*args, **kwargs)
                    raise CircuitBreakerOpenException(self.name)

        try:
            if asyncio.iscoroutinefunction(func):
                res = await func(*args, **kwargs)
            else:
                res = func(*args, **kwargs)
            await self._on_success()
            return res
        except Exception as exc:
            await self._on_failure(exc)
            if fallback:
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                return fallback(*args, **kwargs)
            raise exc

    async def _on_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_success_threshold:
                    logger.info(f"CircuitBreaker[{self.name}] transitioning HALF_OPEN -> CLOSED (Service recovered)")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0  # reset for next HALF_OPEN phase
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def _on_failure(self, exc: Exception):
        async with self._lock:
            self.failure_count += 1
            logger.warning(f"CircuitBreaker[{self.name}] failure {self.failure_count}/{self.failure_threshold}: {exc}")
            if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN) and self.failure_count >= self.failure_threshold:
                logger.error(f"CircuitBreaker[{self.name}] tripping state {self.state} -> OPEN")
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
