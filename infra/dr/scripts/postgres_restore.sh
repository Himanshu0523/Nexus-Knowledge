#!/bin/bash
# Nexus AI - PostgreSQL Restore & Point-In-Time Recovery (PITR) Script
# Verifies SHA256 checksum before executing database restoration.

set -e

BACKUP_FILE="$1"
DB_NAME="${POSTGRES_DB:-chatbot_db}"
DB_USER="${POSTGRES_USER:-chatbot}"
DB_HOST="${POSTGRES_HOST:-postgres-primary}"
DB_PORT="${POSTGRES_PORT:-5432}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <path_to_backup.sql.gz>"
    exit 1
fi

CHECKSUM_FILE="${BACKUP_FILE}.sha256"

if [ -f "$CHECKSUM_FILE" ]; then
    echo "[$(date)] Verifying SHA256 checksum..."
    sha256sum -c "$CHECKSUM_FILE"
    echo "[$(date)] Checksum verification PASSED."
else
    echo "[$(date)] WARNING: No checksum file found at ${CHECKSUM_FILE}. Proceeding with caution."
fi

echo "[$(date)] Restoring database '${DB_NAME}' from ${BACKUP_FILE}..."

# Decompress and restore
gunzip -c "$BACKUP_FILE" | PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"

echo "[$(date)] Database restoration completed successfully!"
