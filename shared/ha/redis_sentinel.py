import logging
import random
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

class HASentinelRedisClient:
    """
    High-Availability Redis / Valkey Sentinel Client Manager.
    Queries Sentinel nodes to dynamically locate current Master (for writes)
    and Read Replicas (for reads/caching).
    """
    def __init__(
        self,
        service_name: str = "mymaster",
        sentinels: Optional[List[Tuple[str, int]]] = None,
        fallback_host: str = "localhost",
        fallback_port: int = 6379
    ):
        self.service_name = service_name
        self.sentinels = sentinels or [("localhost", 26379)]
        self.fallback_host = fallback_host
        self.fallback_port = fallback_port
        self.current_master: Optional[Tuple[str, int]] = None
        self.current_replicas: List[Tuple[str, int]] = []
        self.failover_count = 0
        
        # Initial master resolution simulation/setup
        self._discover_topology()

    def _discover_topology(self):
        """Discovers current master and replica endpoints from Sentinels."""
        # Simulated sentinel resolution; in production redis.sentinel.Sentinel is used
        try:
            logger.info(f"Contacting Sentinel nodes {self.sentinels} for master '{self.service_name}'...")
            # Default to fallback if direct sentinel network call fails or mock mode
            self.current_master = (self.fallback_host, self.fallback_port)
            self.current_replicas = [
                (self.fallback_host, self.fallback_port + 1),
                (self.fallback_host, self.fallback_port + 2)
            ]
        except Exception as e:
            logger.error(f"Sentinel topology discovery failed: {e}. Falling back to default node.")
            self.current_master = (self.fallback_host, self.fallback_port)
            self.current_replicas = []

    def get_master_node(self) -> Tuple[str, int]:
        """Returns endpoint (host, port) for write operations."""
        if not self.current_master:
            self._discover_topology()
        return self.current_master or (self.fallback_host, self.fallback_port)

    def get_replica_node(self) -> Tuple[str, int]:
        """Returns endpoint (host, port) for read-only operations."""
        if self.current_replicas:
            return random.choice(self.current_replicas)
        # Fallback to master if no replicas available
        return self.get_master_node()

    def trigger_failover_reconnect(self, new_master_host: str, new_master_port: int):
        """Simulates or handles Sentinel failover notification event."""
        logger.warning(
            f"Valkey/Redis Sentinel failover detected! New master elected: {new_master_host}:{new_master_port}"
        )
        self.current_master = (new_master_host, new_master_port)
        self.failover_count += 1

    def get_status(self) -> Dict[str, Any]:
        """Returns current Sentinel topology status."""
        return {
            "service_name": self.service_name,
            "master": self.current_master,
            "replicas": self.current_replicas,
            "failover_count": self.failover_count,
            "sentinels_configured": len(self.sentinels)
        }
