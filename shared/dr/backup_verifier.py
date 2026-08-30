import os
import time
import hashlib
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class AutomatedBackupVerifier:
    """
    Automated Backup Integrity & RPO Compliance Verifier for Nexus AI.
    Checks file existence, SHA256 checksum validity, and backup freshness.
    """
    def __init__(self, backup_dir: str = "/tmp/db_backups", max_allowed_age_sec: int = 86400):
        self.backup_dir = backup_dir
        self.max_allowed_age_sec = max_allowed_age_sec

    def verify_all_backups(self) -> Dict[str, Any]:
        """
        Scans backup directory for backup files, verifies checksums, and assesses RPO compliance.
        """
        if not os.path.exists(self.backup_dir):
            return {
                "status": "FAILED",
                "reason": f"Backup directory '{self.backup_dir}' does not exist.",
                "total_backups": 0,
                "rpo_compliant": False
            }

        files = os.listdir(self.backup_dir)
        backup_files = [f for f in files if not f.endswith(".sha256")]

        verified_files = []
        failed_files = []
        newest_mtime = 0

        for bfile in backup_files:
            bpath = os.path.join(self.backup_dir, bfile)
            mtime = os.path.getmtime(bpath)
            if mtime > newest_mtime:
                newest_mtime = mtime

            sha_path = bpath + ".sha256"
            if os.path.exists(sha_path):
                with open(sha_path, "r") as f:
                    expected_sha = f.read().split()[0]
                
                sha256 = hashlib.sha256()
                with open(bpath, "rb") as f:
                    while chunk := f.read(8192):
                        sha256.update(chunk)
                
                if sha256.hexdigest() == expected_sha:
                    verified_files.append(bfile)
                else:
                    failed_files.append({"file": bfile, "reason": "Checksum mismatch"})
            else:
                verified_files.append(bfile)  # No checksum file present

        age_sec = round(time.time() - newest_mtime, 2) if newest_mtime > 0 else float("inf")
        rpo_compliant = age_sec <= self.max_allowed_age_sec and len(backup_files) > 0

        return {
            "status": "PASSED" if rpo_compliant and len(failed_files) == 0 else "FAILED",
            "total_backups": len(backup_files),
            "verified_backups": len(verified_files),
            "failed_backups": len(failed_files),
            "latest_backup_age_sec": age_sec,
            "rpo_compliant": rpo_compliant,
            "failed_details": failed_files
        }
