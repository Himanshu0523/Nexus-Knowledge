import pytest
import os
import yaml
from shared.ha.db_routing import HARoutedDatabasePool, DatabaseNode
from shared.ha.redis_sentinel import HASentinelRedisClient
from shared.ha.qdrant_ha import HAQdrantClusterClient

def test_database_routing_write_always_primary():
    primary_dsn = "postgresql://user:pass@primary:5432/db"
    replica_dsns = ["postgresql://user:pass@replica1:5432/db", "postgresql://user:pass@replica2:5432/db"]
    
    pool = HARoutedDatabasePool(primary_dsn=primary_dsn, replica_dsns=replica_dsns)
    
    # Write operations must ALWAYS hit Primary DSN
    write_dsn = pool.get_connection_dsn(is_write=True)
    assert write_dsn == primary_dsn

def test_database_routing_read_uses_replicas_and_fallback():
    primary_dsn = "postgresql://user:pass@primary:5432/db"
    replica_dsns = ["postgresql://user:pass@replica1:5432/db", "postgresql://user:pass@replica2:5432/db"]
    
    pool = HARoutedDatabasePool(primary_dsn=primary_dsn, replica_dsns=replica_dsns)
    
    # Read query should hit one of the replicas
    read_dsn = pool.get_connection_dsn(is_write=False)
    assert read_dsn in replica_dsns
    
    # Simulate failure of all replicas
    for replica_dsn in replica_dsns:
        pool.report_node_status(replica_dsn, success=False)
        pool.report_node_status(replica_dsn, success=False)
        
    status = pool.get_cluster_status()
    assert status["healthy_read_nodes"] == 1  # Only Primary is left healthy
    
    # Read query must fall back to Primary DSN seamlessly
    fallback_read_dsn = pool.get_connection_dsn(is_write=False)
    assert fallback_read_dsn == primary_dsn

def test_redis_sentinel_failover():
    sentinels = [("localhost", 26379), ("localhost", 26380)]
    client = HASentinelRedisClient(service_name="mymaster", sentinels=sentinels, fallback_host="redis-master", fallback_port=6379)
    
    master = client.get_master_node()
    assert master == ("redis-master", 6379)
    
    # Simulate Sentinel failover to a new master host/port
    client.trigger_failover_reconnect(new_master_host="redis-master-new", new_master_port=6380)
    
    new_master = client.get_master_node()
    assert new_master == ("redis-master-new", 6380)
    assert client.get_status()["failover_count"] == 1

def test_qdrant_ha_cluster_node_fallback():
    nodes = ["http://qdrant-node1:6333", "http://qdrant-node2:6333"]
    qdrant_ha = HAQdrantClusterClient(node_urls=nodes, replication_factor=2)
    
    active_1 = qdrant_ha.get_active_node()
    assert active_1 in nodes
    
    # Report error on current active node
    qdrant_ha.report_node_error(active_1)
    
    active_2 = qdrant_ha.get_active_node()
    assert active_2 != active_1
    assert active_2 in nodes
    
    info = qdrant_ha.get_cluster_info()
    assert info["healthy_nodes"] == 1
    assert active_1 in info["degraded_nodes"]

def test_k8s_ha_manifests_validation():
    k8s_dir = os.path.join(os.path.dirname(__file__), "..", "infra", "k8s")
    
    # Validate API Gateway HA manifest
    api_gw_path = os.path.join(k8s_dir, "api-gateway-ha.yaml")
    assert os.path.exists(api_gw_path)
    with open(api_gw_path, "r") as f:
        docs = list(yaml.safe_load_all(f))
        deploy = docs[0]
        assert deploy["spec"]["replicas"] >= 3
        assert deploy["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == 0

    # Validate Chat Service HA manifest
    chat_svc_path = os.path.join(k8s_dir, "chat-service-ha.yaml")
    assert os.path.exists(chat_svc_path)
    with open(chat_svc_path, "r") as f:
        docs = list(yaml.safe_load_all(f))
        deploy = docs[0]
        assert deploy["spec"]["replicas"] >= 3
        assert deploy["spec"]["strategy"]["type"] == "RollingUpdate"

    # Validate PodDisruptionBudget manifest
    pdb_path = os.path.join(k8s_dir, "pod-disruption-budgets.yaml")
    assert os.path.exists(pdb_path)
    with open(pdb_path, "r") as f:
        docs = list(yaml.safe_load_all(f))
        assert len(docs) >= 3
