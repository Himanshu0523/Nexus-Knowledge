from enum import Enum
import time
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operational state
    OPEN = "OPEN"          # Circuit tripped (unhealthy, skip calls)
    HALF_OPEN = "HALF_OPEN"# Probing health state after recovery period

class BackendCircuit:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_cooldown: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_cooldown = recovery_cooldown
        
        self.state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.total_requests: int = 0
        self.total_errors: int = 0
        self.last_failure_time: float = 0.0
        self.last_success_time: float = 0.0

    def is_available(self) -> bool:
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery cooldown period has elapsed
            if now - self.last_failure_time >= self.recovery_cooldown:
                logger.info(f"Circuit breaker for backend '{self.name}' transitioning to HALF_OPEN (probing)")
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return True

    def record_success(self):
        self.total_requests += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()
        if self.state != CircuitState.CLOSED:
            logger.info(f"Backend '{self.name}' recovered! Circuit state returned to CLOSED.")
            self.state = CircuitState.CLOSED

    def record_failure(self, error: Optional[Exception] = None):
        self.total_requests += 1
        self.total_errors += 1
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        if self.consecutive_failures >= self.failure_threshold and self.state != CircuitState.OPEN:
            logger.warning(
                f"Backend '{self.name}' hit failure threshold ({self.consecutive_failures}/{self.failure_threshold}). "
                f"Tripping circuit breaker to OPEN!"
            )
            self.state = CircuitState.OPEN

class CircuitBreaker:
    """
    Manages circuit breaker instances across registered LLM backends.
    """

    def __init__(self, failure_threshold: int = 3, recovery_cooldown: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_cooldown = recovery_cooldown
        self.circuits: Dict[str, BackendCircuit] = {}

    def get_circuit(self, name: str) -> BackendCircuit:
        if name not in self.circuits:
            self.circuits[name] = BackendCircuit(
                name=name,
                failure_threshold=self.failure_threshold,
                recovery_cooldown=self.recovery_cooldown
            )
        return self.circuits[name]

    def is_available(self, name: str) -> bool:
        return self.get_circuit(name).is_available()

    def record_success(self, name: str):
        self.get_circuit(name).record_success()

    def record_failure(self, name: str, error: Optional[Exception] = None):
        self.get_circuit(name).record_failure(error)

    def get_state(self, name: str) -> str:
        return self.get_circuit(name).state.value

    def reset(self, name: str):
        circuit = self.get_circuit(name)
        circuit.state = CircuitState.CLOSED
        circuit.consecutive_failures = 0
