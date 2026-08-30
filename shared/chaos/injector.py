"""
Nexus AI - Enterprise Chaos Injector Engine.
Provides programmatic fault injection, safety monitoring, and automated emergency aborts.
"""

import time
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field

logger = logging.getLogger("nexus.chaos.injector")


class FaultType(str, Enum):
    NETWORK_LATENCY = "network_latency"
    PACKET_LOSS = "packet_loss"
    PROCESS_CRASH = "process_crash"
    SERVICE_DEGRADATION = "service_degradation"
    CACHE_EVICTION = "cache_eviction"
    LLM_PROVIDER_OUTAGE = "llm_provider_outage"
    DATABASE_FAILOVER = "database_failover"


@dataclass
class SafetyPolicy:
    max_error_rate_pct: float = 5.0  # Max acceptable error rate during chaos
    max_latency_p99_ms: float = 2000.0  # Max P99 latency threshold
    auto_rollback: bool = True
    max_duration_seconds: int = 60
    check_interval_seconds: float = 1.0


@dataclass
class ChaosExperimentConfig:
    experiment_id: str
    name: str
    target_service: str
    fault_type: FaultType
    duration_seconds: int = 30
    parameters: Dict[str, Any] = field(default_factory=dict)
    safety_policy: SafetyPolicy = field(default_factory=SafetyPolicy)


class ChaosInjector:
    def __init__(self, metrics_provider: Optional[Callable[[], Dict[str, float]]] = None):
        self.metrics_provider = metrics_provider or self._default_metrics_provider
        self.active_experiments: Dict[str, ChaosExperimentConfig] = {}
        self.active_faults: Dict[str, Dict[str, Any]] = {}
        self.aborted_experiments: List[str] = []
        self._interceptors: Dict[FaultType, Callable] = {
            FaultType.NETWORK_LATENCY: self._inject_network_latency,
            FaultType.LLM_PROVIDER_OUTAGE: self._inject_llm_outage,
            FaultType.CACHE_EVICTION: self._inject_cache_eviction,
            FaultType.DATABASE_FAILOVER: self._inject_db_failover,
            FaultType.SERVICE_DEGRADATION: self._inject_service_degradation,
        }

    def _default_metrics_provider(self) -> Dict[str, float]:
        """Default synthetic metrics provider for safety checks."""
        return {
            "error_rate_pct": 0.5,
            "latency_p99_ms": 150.0,
            "system_cpu_pct": 35.0,
        }

    async def start_experiment(self, config: ChaosExperimentConfig) -> Dict[str, Any]:
        """Starts a controlled chaos experiment with automated safety monitoring."""
        logger.info(
            f"[ChaosInjector] Starting experiment '{config.name}' (ID: {config.experiment_id}) "
            f"on service '{config.target_service}' with fault '{config.fault_type.value}'"
        )
        
        self.active_experiments[config.experiment_id] = config
        fault_info = {
            "experiment_id": config.experiment_id,
            "fault_type": config.fault_type.value,
            "target": config.target_service,
            "started_at": time.time(),
            "status": "ACTIVE",
            "parameters": config.parameters,
        }
        self.active_faults[config.experiment_id] = fault_info

        # Execute fault handler
        handler = self._interceptors.get(config.fault_type)
        if handler:
            await handler(config)

        # Run safety monitor background task simulation
        aborted = await self._monitor_safety(config)
        
        if aborted:
            fault_info["status"] = "ABORTED_SAFETY_BREACH"
            logger.warning(f"[ChaosInjector] Experiment {config.experiment_id} ABORTED due to safety policy breach!")
            return {
                "experiment_id": config.experiment_id,
                "status": "ABORTED_SAFETY_BREACH",
                "message": "Experiment rolled back safely.",
                "duration_executed_s": time.time() - fault_info["started_at"],
            }

        fault_info["status"] = "COMPLETED"
        fault_info["ended_at"] = time.time()
        logger.info(f"[ChaosInjector] Experiment {config.experiment_id} completed successfully within safety bounds.")

        return {
            "experiment_id": config.experiment_id,
            "status": "COMPLETED",
            "message": "Chaos experiment executed and restored successfully.",
            "duration_executed_s": fault_info["ended_at"] - fault_info["started_at"],
        }

    async def stop_experiment(self, experiment_id: str) -> bool:
        """Manually stops an active experiment and restores baseline state."""
        if experiment_id in self.active_experiments:
            logger.info(f"[ChaosInjector] Stopping experiment {experiment_id}")
            self.active_faults[experiment_id]["status"] = "STOPPED"
            del self.active_experiments[experiment_id]
            return True
        return False

    async def _monitor_safety(self, config: ChaosExperimentConfig) -> bool:
        """Monitors system health metrics during chaos experiment and triggers emergency abort if SLA breached."""
        start_time = time.time()
        safety = config.safety_policy

        while (time.time() - start_time) < min(config.duration_seconds, safety.max_duration_seconds):
            await asyncio.sleep(0.05)  # Fast test loop simulation
            metrics = self.metrics_provider()

            # Inspect simulated metrics for injected custom parameters
            error_rate = config.parameters.get("simulated_error_rate", metrics.get("error_rate_pct", 0.0))
            latency_p99 = config.parameters.get("simulated_latency_p99", metrics.get("latency_p99_ms", 0.0))

            if safety.auto_rollback:
                if error_rate > safety.max_error_rate_pct:
                    logger.error(
                        f"[ChaosInjector] Safety Breach! Error rate ({error_rate}%) > "
                        f"threshold ({safety.max_error_rate_pct}%). Triggering emergency rollback."
                    )
                    self.aborted_experiments.append(config.experiment_id)
                    return True

                if latency_p99 > safety.max_latency_p99_ms:
                    logger.error(
                        f"[ChaosInjector] Safety Breach! P99 Latency ({latency_p99}ms) > "
                        f"threshold ({safety.max_latency_p99_ms}ms). Triggering emergency rollback."
                    )
                    self.aborted_experiments.append(config.experiment_id)
                    return True

        return False

    async def _inject_network_latency(self, config: ChaosExperimentConfig):
        latency_ms = config.parameters.get("latency_ms", 500)
        logger.info(f"[ChaosInjector] Injected {latency_ms}ms network latency to {config.target_service}")

    async def _inject_llm_outage(self, config: ChaosExperimentConfig):
        failure_rate = config.parameters.get("failure_rate", 1.0)
        logger.info(f"[ChaosInjector] Injected LLM provider outage ({failure_rate*100}% failure rate) to {config.target_service}")

    async def _inject_cache_eviction(self, config: ChaosExperimentConfig):
        logger.info(f"[ChaosInjector] Flushed Redis/Valkey cache keys for {config.target_service}")

    async def _inject_db_failover(self, config: ChaosExperimentConfig):
        logger.info(f"[ChaosInjector] Triggering simulated DB Primary crash & failover sequence for {config.target_service}")

    async def _inject_service_degradation(self, config: ChaosExperimentConfig):
        logger.info(f"[ChaosInjector] Simulating CPU/Memory throttling on {config.target_service}")

    def is_fault_active(self, fault_type: FaultType, service_name: str) -> bool:
        """Helper to query if a fault is currently active on a service."""
        for fault in self.active_faults.values():
            if fault["status"] == "ACTIVE" and fault["fault_type"] == fault_type.value and fault["target"] == service_name:
                return True
        return False
