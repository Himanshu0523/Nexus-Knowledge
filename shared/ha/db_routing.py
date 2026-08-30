import logging
import random
import time
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

class DatabaseNode:
    """Represents a single PostgreSQL node (Primary or Read Replica)."""
    def __init__(self, dsn: str, is_primary: bool = False, name: str = "node"):
        self.dsn = dsn
        self.is_primary = is_primary
        self.name = name
        self.is_healthy = True
        self.consecutive_failures = 0
        self.last_check_time = 0.0

    def mark_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= 2:
            self.is_healthy = False
            logger.warning(f"Database node '{self.name}' marked UNHEALTHY after {self.consecutive_failures} failures.")

    def mark_success(self):
        self.consecutive_failures = 0
        if not self.is_healthy:
            logger.info(f"Database node '{self.name}' recovered and marked HEALTHY.")
            self.is_healthy = True

class HARoutedDatabasePool:
    """
    High-Availability PostgreSQL Router.
    Directs write queries (`INSERT`, `UPDATE`, `DELETE`) to the Primary instance,
    and balances read queries (`SELECT`) across available Read Replicas.
    Falls back to Primary for reads if all replicas are degraded or unavailable.
    """
    def __init__(self, primary_dsn: str, replica_dsns: Optional[List[str]] = None):
        self.primary = DatabaseNode(primary_dsn, is_primary=True, name="primary-0")
        self.replicas: List[DatabaseNode] = []
        if replica_dsns:
            for idx, dsn in enumerate(replica_dsns):
                self.replicas.append(DatabaseNode(dsn, is_primary=False, name=f"replica-{idx+1}"))
        
        logger.info(
            f"HARoutedDatabasePool initialized. Primary: {self.primary.name}, Replicas: {len(self.replicas)}"
        )

    def get_connection_dsn(self, is_write: bool = False) -> str:
        """
        Retrieves the appropriate DSN for a database operation.
        Write operations ALWAYS route to Primary.
        Read operations route to a healthy replica, or fall back to Primary if none available.
        """
        if is_write:
            if not self.primary.is_healthy:
                logger.error("Primary database is currently flagged UNHEALTHY! Attempting reconnect.")
            return self.primary.dsn

        # Read operation: find healthy replicas
        healthy_replicas = [r for r in self.replicas if r.is_healthy]
        if healthy_replicas:
            # Load balance randomly / round-robin across healthy replicas
            selected = random.choice(healthy_replicas)
            logger.debug(f"Routing read query to replica: {selected.name}")
            return selected.dsn
        
        # Fallback to Primary if no replicas are healthy
        if self.replicas:
            logger.warning("No healthy read replicas available. Falling back read query to Primary node.")
        return self.primary.dsn

    def report_node_status(self, dsn: str, success: bool):
        """Updates health status of a node based on query execution success/failure."""
        if dsn == self.primary.dsn:
            if success:
                self.primary.mark_success()
            else:
                self.primary.mark_failure()
            return

        for replica in self.replicas:
            if replica.dsn == dsn:
                if success:
                    replica.mark_success()
                else:
                    replica.mark_failure()
                break

    def get_cluster_status(self) -> Dict[str, Any]:
        """Returns diagnostic health metrics for all database nodes in the HA pool."""
        return {
            "primary": {
                "name": self.primary.name,
                "healthy": self.primary.is_healthy,
                "failures": self.primary.consecutive_failures
            },
            "replicas": [
                {
                    "name": r.name,
                    "healthy": r.is_healthy,
                    "failures": r.consecutive_failures
                }
                for r in self.replicas
            ],
            "total_nodes": 1 + len(self.replicas),
            "healthy_read_nodes": len([r for r in self.replicas if r.is_healthy]) + (1 if self.primary.is_healthy else 0)
        }
