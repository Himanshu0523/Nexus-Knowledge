import os
import time
import shutil
import pytest
from infra.dr.scripts.qdrant_snapshot import QdrantSnapshotManager
from infra.dr.scripts.valkey_backup import ValkeyBackupManager
from shared.dr.failover import ActivePassiveFailoverOrchestrator, RegionState
from shared.dr.backup_verifier import AutomatedBackupVerifier

@pytest.fixture
def temp_backup_dir(tmp_path):
    backup_dir = str(tmp_path / "dr_backups")
    os.makedirs(backup_dir, exist_ok=True)
    yield backup_dir
    shutil.rmtree(backup_dir, ignore_errors=True)

def test_qdrant_snapshot_creation_and_verification(temp_backup_dir):
    manager = QdrantSnapshotManager(backup_dir=temp_backup_dir)
    res = manager.create_collection_snapshot(collection_name="test_collection")
    
    assert os.path.exists(res["snapshot_file"])
    assert os.path.exists(res["checksum_file"])
    assert manager.verify_snapshot(res["snapshot_file"]) is True

def test_valkey_backup_creation_and_verification(temp_backup_dir):
    manager = ValkeyBackupManager(backup_dir=temp_backup_dir)
    res = manager.trigger_bgsave_backup()
    
    assert res["status"] == "SUCCESS"
    assert os.path.exists(res["backup_file"])
    assert manager.verify_backup(res["backup_file"]) is True

def test_active_passive_failover_orchestration():
    orchestrator = ActivePassiveFailoverOrchestrator(
        primary_region="us-east-1",
        secondary_region="us-west-2",
        heartbeat_threshold=3
    )
    
    # 1. Primary region is healthy
    assert orchestrator.record_heartbeat(is_healthy=True) == RegionState.PRIMARY_ACTIVE
    
    # 2. First failure -> PRIMARY_DEGRADED
    assert orchestrator.record_heartbeat(is_healthy=False) == RegionState.PRIMARY_DEGRADED
    
    # 3. Second failure -> PRIMARY_DEGRADED
    assert orchestrator.record_heartbeat(is_healthy=False) == RegionState.PRIMARY_DEGRADED
    
    # 4. Third failure (threshold reached) -> SECONDARY_ACTIVE
    state = orchestrator.record_heartbeat(is_healthy=False)
    assert state == RegionState.SECONDARY_ACTIVE
    assert orchestrator.active_region == "us-west-2"
    
    status = orchestrator.get_cluster_status()
    assert status["total_failovers"] == 1
    assert status["current_state"] == RegionState.SECONDARY_ACTIVE.value

def test_automated_backup_verifier(temp_backup_dir):
    # Create mock backup and sha256 checksum file
    backup_file = os.path.join(temp_backup_dir, "postgres_chatbot_db_20260830.sql.gz")
    with open(backup_file, "w") as f:
        f.write("MOCK_SQL_DATA")

    import hashlib
    sha256 = hashlib.sha256(b"MOCK_SQL_DATA").hexdigest()
    with open(backup_file + ".sha256", "w") as f:
        f.write(f"{sha256}  postgres_chatbot_db_20260830.sql.gz\n")

    verifier = AutomatedBackupVerifier(backup_dir=temp_backup_dir, max_allowed_age_sec=3600)
    report = verifier.verify_all_backups()
    
    assert report["status"] == "PASSED"
    assert report["total_backups"] == 1
    assert report["verified_backups"] == 1
    assert report["failed_backups"] == 0
    assert report["rpo_compliant"] is True
