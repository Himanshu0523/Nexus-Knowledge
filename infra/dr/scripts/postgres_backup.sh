#!/bin/bash
# Nexus AI - Automated PostgreSQL Backup & S3 Upload Script
# Executes pg_dump / pg_basebackup with gzip compression and SHA256 checksum generation.

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-/tmp/db_backups}"
DB_NAME="${POSTGRES_DB:-chatbot_db}"
DB_USER="${POSTGRES_USER:-chatbot}"
DB_HOST="${POSTGRES_HOST:-postgres-primary}"
DB_PORT="${POSTGRES_PORT:-5432}"
S3_BUCKET="${DR_BACKUP_S3_BUCKET:-s3://nexus-ai-backups/postgres}"

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="${BACKUP_DIR}/postgres_${DB_NAME}_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

echo "[$(date)] Starting PostgreSQL full backup for database '${DB_NAME}'..."

# Run pg_dump with compression
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" | gzip > "$BACKUP_FILE"

# Generate SHA256 checksum
sha256sum "$BACKUP_FILE" > "$CHECKSUM_FILE"

echo "[$(date)] Backup completed successfully: ${BACKUP_FILE}"
echo "[$(date)] Checksum created: ${CHECKSUM_FILE}"

# Upload to S3 if AWS CLI is configured
if command -v aws &> /dev/null; then
    echo "[$(date)] Uploading backup to remote S3 bucket ${S3_BUCKET}..."
    aws s3 cp "$BACKUP_FILE" "${S3_BUCKET}/"
    aws s3 cp "$CHECKSUM_FILE" "${S3_BUCKET}/"
    echo "[$(date)] S3 Upload finished successfully."
else
    echo "[$(date)] AWS CLI not found. Backup stored locally at ${BACKUP_FILE}"
fi
