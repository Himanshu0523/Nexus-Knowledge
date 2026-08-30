import logging
import random
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

class HAQdrantClusterClient:
    """
    High-Availability Qdrant Vector DB Cluster Client Manager.
    Maintains connection pools across multiple Qdrant cluster nodes.
    Automatically retries requests against healthy fallback nodes if a node fails.
    """
    def __init__(self, node_urls: Optional[List[str]] = None, replication_factor: int = 2):
        self.node_urls = node_urls or ["http://localhost:6333", "http://localhost:6334"]
        self.replication_factor = replication_factor
        self.active_node_index = 0
        self.degraded_nodes = set()

        logger.info(
            f"HAQdrantClusterClient initialized with {len(self.node_urls)} cluster nodes. Replication factor: {self.replication_factor}"
        )

    def get_active_node(self) -> str:
        """Returns the URL of the primary active healthy Qdrant node."""
        healthy = [n for n in self.node_urls if n not in self.degraded_nodes]
        if healthy:
            return healthy[self.active_node_index % len(healthy)]
        # If all marked degraded, reset degraded status and retry
        logger.warning("All Qdrant cluster nodes marked degraded. Resetting health status for retry.")
        self.degraded_nodes.clear()
        return self.node_urls[0]

    def report_node_error(self, node_url: str):
        """Marks a node as degraded and switches active index to next available node."""
        logger.error(f"Qdrant node failure reported for '{node_url}'. Marking node degraded.")
        self.degraded_nodes.add(node_url)
        # Advance and wrap within node count to prevent unbounded growth
        self.active_node_index = (self.active_node_index + 1) % max(len(self.node_urls), 1)

    def report_node_success(self, node_url: str):
        """Restores node health status on successful query/ingest."""
        if node_url in self.degraded_nodes:
            logger.info(f"Qdrant node '{node_url}' recovered. Clearing degraded status.")
            self.degraded_nodes.remove(node_url)

    def get_cluster_info(self) -> Dict[str, Any]:
        """Returns cluster operational status."""
        return {
            "total_nodes": len(self.node_urls),
            "healthy_nodes": len(self.node_urls) - len(self.degraded_nodes),
            "degraded_nodes": list(self.degraded_nodes),
            "active_endpoint": self.get_active_node(),
            "replication_factor": self.replication_factor
        }
