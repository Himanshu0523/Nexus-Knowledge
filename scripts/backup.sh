#!/bin/bash

set -e

BACKUP_DIR=${BACKUP_DIR:-/backups}
DATABASE_URL=${DATABASE_URL:-postgresql://chatbot:chatbot_password@localhost:5432/chatbot_db}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "Backing up PostgreSQL..."
pg_dump $DATABASE_URL > $BACKUP_DIR/postgres_$TIMESTAMP.sql
gzip $BACKUP_DIR/postgres_$TIMESTAMP.sql

echo "Backup complete: $BACKUP_DIR/postgres_$TIMESTAMP.sql.gz"
